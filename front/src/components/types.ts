export type Player = "first" | "second";

export interface PlayerInfo {
    name: string;
    score: number;
}

export interface GameData {
    "first": PlayerInfo,
    "second": PlayerInfo,
    "point_match": number | null,
    "turns": Turn[]
}

export interface Move {
    "from": string,
    "to": string,
    "captured": boolean
}

export interface Turn {
    turn: Player;
    dice: [number, number];
    cube_owner: Player | null;
    cube_value: number;
    cube_location: 'center' | Player | null; // добавлено
    moves: Move[];
    action?: 'double' | 'take' | 'drop';
}


export type CheckerData = {
    id: string;
    player: Player;
    index: number;
    x: number;
    y: number;
    direction: 1 | -1;
    sortOrder: number;
    currentPosition: string;
    check: boolean;
    delay?: number;
};