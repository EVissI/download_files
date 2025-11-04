import * as fs from 'fs/promises';
import * as path from 'path';
import {GameData, Move as ParsedMove, Player} from "@/components/types";

type PlayerKey = 'player1' | 'player2';
type PlayerId = 'first' | 'second';

interface Move {
    move: number;
    player1: string;
    player2: string;
    dice1: number[];
    dice2: number[];
}

interface ExtractedNames {
    first_name: string;
    first_score: number;
    second_name: string;
    second_score: number;
}

function togglePlayer(player: Player, first: PlayerId, second: PlayerId): Player {
    return player === 'first' ? second : first;
}

function parseMoveTable(lines: string[]): Move[] {
    const result: Move[] = [];
    const pattern = /^\s*(\d+)\)\s*(.*?)\s{2,}(.*?)\s*$/;

    for (let line of lines) {
        line = line.trimEnd();
        const match = line.match(pattern);
        if (!match) continue;

        const move_number = parseInt(match[1], 10);
        const player1_text = match[2].trim();
        const player2_text = match[3].trim();

        function extractDice(s: string): number[] {
            const diceMatch = s.match(/^(\d{2}):/);
            if (diceMatch) {
                return [parseInt(s[0], 10), parseInt(s[1], 10)];
            }
            return [];
        }

        const dice1 = extractDice(player1_text);
        const dice2 = extractDice(player2_text);

        result.push({
            move: move_number,
            player1: player1_text,
            player2: player2_text,
            dice1,
            dice2,
        });
    }

    return result;
}

function extractNamesAndScores(lines: string[]): ExtractedNames {
    const pattern = /^(.*?)\s*:\s*(\d+)\s+(.*?)\s*:\s*(\d+)\s*$/;
    for (const line of lines) {
        const match = line.match(pattern);
        if (match) {
            return {
                first_name: match[1].trim(),
                first_score: parseInt(match[2], 10),
                second_name: match[3].trim(),
                second_score: parseInt(match[4], 10),
            };
        }
    }
    return {
        first_name: 'Player 1',
        first_score: 0,
        second_name: 'Player 2',
        second_score: 0,
    };
}

function extractPointMatch(text: string): number | null {
    const pattern = /(\d+)\s+point match/i;
    const match = text.match(pattern);
    return match ? parseInt(match[1], 10) : null;
}

function extractGameType(text: string): boolean {
    return /Game type: Backgammon\s\+1/im.test(text);
}

function extractMoves(playerMoves: string): ParsedMove[] {
    const movesList: ParsedMove[] = [];
    const splitMoves = playerMoves.split(': ');
    if (splitMoves.length === 1) return movesList;

    for (const move of splitMoves[1].split(' ')) {
        if (!move.includes('/')) continue;
        let [start, end] = move.split('/');
        let captured = false;
        if (end.endsWith('*')) {
            captured = true;
            end = end.slice(0, -1);
        }
        movesList.push({from: start, to: end, captured});
    }
    return movesList;
}

async function parseGame(text: string, pointsMatch: number | null, isLongGame: boolean, isInverse: boolean): Promise<GameData> {
    const [first, second]: ['first', 'second'] | ['second', 'first'] = isInverse ? ['second', 'first'] : ['first', 'second'];
    const lines = text.trim().split('\n');
    const headerData = extractNamesAndScores(lines);

    const gameData: GameData = {
        [first]: {name: headerData.first_name, score: headerData.first_score},
        [second]: {name: headerData.second_name, score: headerData.second_score},
        point_match: pointsMatch,
        is_long_game: isLongGame,
        turns: [],
    };

    let cubeOwner: Player | null = null;
    let cubeValue = 1;
    let cubeLocation: 'center' | Player | null = null;

    const moves = parseMoveTable(lines);

    for (const move of moves) {
        for (const playerKey of ['player1', 'player2'] as PlayerKey[]) {
            const player: Player = playerKey === 'player1' ? first : second;
            const textMove = move[playerKey];
            if (!textMove) continue;

            if (textMove.includes('Doubles =>')) {
                cubeValue = parseInt(textMove.split('=>')[1].trim(), 10);
                cubeOwner = togglePlayer(player, first, second); // ставит куб противнику (тот, кто принимает)
                cubeLocation = 'center'; // при двойном куб ставится в центр
                gameData.turns.push({
                    turn: player,
                    dice: [0, 0],
                    cube_owner: cubeOwner,
                    cube_value: cubeValue,
                    cube_location: cubeLocation,
                    moves: [],
                    action: 'double',
                });
                continue;
            }

            if (textMove.includes('Takes')) {
                cubeLocation = player; // принимающий забирает куб к себе
                gameData.turns.push({
                    turn: player,
                    dice: [0, 0],
                    cube_owner: cubeOwner,
                    cube_value: cubeValue,
                    cube_location: cubeLocation,
                    moves: [],
                    action: 'take',
                });
                continue;
            }

            if (textMove.includes('Drops')) {
                cubeLocation = null; // сброс куба, игра заканчивается
                gameData.turns.push({
                    turn: player,
                    dice: [0, 0],
                    cube_owner: cubeOwner,
                    cube_value: cubeValue,
                    cube_location: cubeLocation,
                    moves: [],
                    action: 'drop',
                });
                continue;
            }

            const dice = playerKey === 'player1' ? move.dice1 : move.dice2;
            const movesList = extractMoves(textMove);

            gameData.turns.push({
                turn: player,
                dice: dice as [number, number],
                cube_owner: cubeOwner,
                cube_value: cubeValue,
                cube_location: cubeLocation,
                moves: movesList,
            });
        }
    }

    return gameData;
}


export async function parseFile(data: string, dir: string, isInverse: boolean): Promise<number> {
    const splitFile = data.split(/\n\nGame \d+\n/);
    const pointsMatch = extractPointMatch(splitFile[0]);
    const gameType = extractGameType(splitFile[0]);
    const gamesRaw = splitFile.slice(1);

    const dirPath = path.resolve('./public/json', dir);
    await fs.mkdir(dirPath, {recursive: true});
    const filePath = path.join(dirPath, 'games.json');

    // Открываем поток записи
    const fileHandle = await fs.open(filePath, 'w');
    await fileHandle.write('[');

    let first = true;
    let count = 0;

    for (const rawGame of gamesRaw) {
        const game = await parseGame(rawGame, pointsMatch, gameType, isInverse);
        const json = JSON.stringify(game, null, 2);

        if (!first) {
            await fileHandle.write(',\n');
        }
        await fileHandle.write(json);
        first = false;
        count++;
    }

    await fileHandle.write(']');
    await fileHandle.close();

    return count;
}

export const getNames = async (data: string): Promise<[string, string]> => {
    const splitFile = data.split(/\n\nGame \d+\n/);
    const gamesRaw = splitFile.slice(1);

    const lines = gamesRaw[0].trim().split('\n');
    const headerData = extractNamesAndScores(lines);
    return [headerData.first_name, headerData.second_name];
}