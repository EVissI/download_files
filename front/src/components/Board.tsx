"use client";
import {useEffect, useRef, useState} from "react";
import {Checker} from "@/components/Checker";
import DiceRoll from "@/components/DiceRoll";
import {
    calculateCordY,
    generateDefaultCheckersData, getCubeCoords,
    getDirection,
    getRealPoint,
    sliceString,
    togglePlayer
} from "@/lib/helpers";
import {BAR_COORDS, POINT_COORDS, ZERO_COORDS} from "@/lib/boardData";
import {CheckerData, GameData, Player} from "@/components/types";


interface IBoardProps {
    gameData?: GameData,
    setIsGameFinished: (a: boolean) => void;
    chatId: string | null;
}


export default function Board({gameData, setIsGameFinished, chatId}: IBoardProps) {
    const [data] = useState<GameData | undefined>(gameData);
    const [currentTurn, setCurrentTurn] = useState(-1);
    const [lastTurn, setLastTurn] = useState(-2);
    const [gameDirection, setGameDirection] = useState(1);
    const [checkers, setCheckers] = useState<CheckerData[]>(generateDefaultCheckersData());
    const [screenPending, setScreenPending] = useState(false);
    const screenBlockRef = useRef<HTMLDivElement | null>(null);
    const turn = data?.turns[currentTurn];
    const cubeCoords = turn ? getCubeCoords(turn.cube_location) : null;
    const [isAnimating, setIsAnimating] = useState(false);

    const handleScreenshot = async () => {
        if (!screenBlockRef.current) return;
        setScreenPending(true);
        await fetch('/api/screenshot', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                state: {
                    checkers,
                    "first": data?.first,
                    "second": data?.second,
                    "point_match": data?.point_match,
                    currentTurn: data?.turns[currentTurn],
                },
                chat_id: chatId,
            }),
        });
        setScreenPending(false);
    };

    useEffect(() => {
        if (!data) return;
        if (!turn) return;
        setIsAnimating(true);

        let maxDelay = 0;

        // Создаем копию массива с обновленными значениями
        let newCheckers = checkers.map(checker => ({
            ...checker,
            check: false,
            delay: 0
        }));

        let i = 0;
        const player = turn.turn;

        const moves = currentTurn > lastTurn ? turn.moves : turn.moves.reverse();

        for (let {from, to, captured} of moves) {
            const otherPlayer = togglePlayer(player);

            if (currentTurn > lastTurn) {
                from = getRealPoint(from, player);
                to = getRealPoint(to, player);
            } else {
                const acc = from;
                from = getRealPoint(to, player);
                to = getRealPoint(acc, player);
            }

            if (captured) {
                if (currentTurn > lastTurn) {
                    const foundChecker = newCheckers.find(el => el.currentPosition === to && el.player === otherPlayer);
                    const found = newCheckers.filter(c => c.currentPosition === 'Bar' && c.player === otherPlayer);
                    const maxIndex = found.reduce((acc, curr) => curr.index > acc ? curr.index : acc, -1);

                    if (foundChecker) {
                        foundChecker.currentPosition = 'Bar';
                        foundChecker.x = BAR_COORDS[otherPlayer].x;
                        foundChecker.index = maxIndex + 1;
                        foundChecker.y = calculateCordY(BAR_COORDS[otherPlayer].y, maxIndex + 1, getDirection('Bar', player), to);
                        foundChecker.check = true;
                        foundChecker.delay = 1 + i * 0.1;
                        i++;
                        maxDelay = Math.max(maxDelay, 1 + i * 0.1);
                    }
                } else {
                    const foundChecker = newCheckers.find(el => el.currentPosition === 'Bar' && el.player === otherPlayer);
                    const found = newCheckers.filter(c => c.currentPosition === from && c.player === otherPlayer);
                    const maxIndex = found.reduce((acc, curr) => curr.index > acc ? curr.index : acc, -1);

                    if (foundChecker) {
                        foundChecker.currentPosition = from;
                        foundChecker.x = POINT_COORDS[from].x;
                        foundChecker.index = maxIndex + 1;
                        foundChecker.y = calculateCordY(POINT_COORDS[from].y, maxIndex + 1, getDirection(to, player), from);
                        foundChecker.check = true;
                        foundChecker.delay = 1 + i * 0.1;
                        i++;
                        maxDelay = Math.max(maxDelay, 1 + i * 0.1);
                    }
                }
            }

            const currentChecker = newCheckers.reduce((acc, curr) => {
                if (Number(from) < 13) {
                    return curr.y < (acc?.y ?? Infinity) && curr.currentPosition === from && curr.player === player ? curr : acc;
                }
                return curr.y > (acc?.y ?? -Infinity) && curr.currentPosition === from && curr.player === player ? curr : acc;
            }, undefined as CheckerData | undefined);

            const maxIndex = newCheckers.reduce((acc, curr) => {
                return curr.index > (acc?.index ?? -Infinity) && curr.currentPosition === to && curr.player === player ? curr : acc;
            }, undefined as CheckerData | undefined)?.index ?? -1;

            if (currentChecker) {
                const coords = to === 'Bar' ? BAR_COORDS[player] : to === "0" ? ZERO_COORDS[player] : POINT_COORDS[to];
                currentChecker.currentPosition = to;
                currentChecker.x = coords.x;
                currentChecker.index = maxIndex + 1;
                currentChecker.y = calculateCordY(coords.y, maxIndex + 1, getDirection(to, player), to);
                currentChecker.check = true;
                currentChecker.delay = 1 + i * 0.1;
                i++;
                maxDelay = Math.max(maxDelay, 1 + i * 0.1);
            }
        }

        setTimeout(() => setIsAnimating(false), (maxDelay + 0.4)*1000);

        // Обновляем состояние
        setCheckers(newCheckers);
    }, [data, currentTurn, lastTurn]);

    if (!data) {
        return (
            <div className="min-h-screen flex justify-center items-center">
                <span className="loader"></span>
            </div>
        );
    }

    return (
        <div className="w-full main p-2 pt-8">
            <div ref={screenBlockRef} style={{backgroundColor: '#fff8e7'}}>
                <div className="header">
                    <div className="header_item justify-start">
                        <div className="checker checker--second">
                            {turn?.turn === 'second' && (turn.action === 'drop' ? (
                                <svg fill="#E53935" viewBox="0 0 16 16"
                                     xmlns="http://www.w3.org/2000/svg" width="60%">
                                    <path
                                        d="M0 14.545L1.455 16 8 9.455 14.545 16 16 14.545 9.455 8 16 1.455 14.545 0 8 6.545 1.455 0 0 1.455 6.545 8z"
                                        fillRule="evenodd"></path>
                                </svg>
                            ) : (
                                <svg className="status" xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="100"
                                     height="100"
                                     viewBox="0 0 48 48">
                                    <path fill="#43A047"
                                          d="M40.6 12.1L17 35.7 7.4 26.1 4.6 29 17 41.3 43.4 14.9z"></path>
                                </svg>))}
                            {turn?.cube_owner === 'second' && turn.action !== 'double' && cubeCoords && (
                                <div
                                    style={{
                                        position: 'absolute',
                                        left: cubeCoords.x,
                                        top: cubeCoords.y,
                                        zIndex: 1000,
                                        borderRadius: 8,
                                        background: 'white',
                                        boxShadow: '0 0 4px #aaa',
                                        border: '1px solid gray',
                                        width: 24,
                                        height: 24,
                                        display: 'flex',
                                        justifyContent: 'center',
                                        alignItems: 'center',
                                        fontSize: 16
                                    }}
                                >
                                    {turn.cube_value}
                                </div>
                            )}
                        </div>
                        <div className="score">{data.second.score}</div>
                    </div>
                    <div className="font-sans p-2 text-lg">:</div>
                    <div className="header_item justify-end">
                        <div className="score">{data.first.score}</div>
                        <div className="checker checker--first">
                            {turn?.turn === 'first' && (turn.action === 'drop' ? (
                                <svg fill="#E53935" viewBox="0 0 16 16"
                                     xmlns="http://www.w3.org/2000/svg" width="60%">
                                    <path
                                        d="M0 14.545L1.455 16 8 9.455 14.545 16 16 14.545 9.455 8 16 1.455 14.545 0 8 6.545 1.455 0 0 1.455 6.545 8z"
                                        fillRule="evenodd"></path>
                                </svg>
                            ) : (
                                <svg className="status" xmlns="http://www.w3.org/2000/svg"
                                     viewBox="0 0 48 48">
                                    <path fill="#43A047"
                                          d="M40.6 12.1L17 35.7 7.4 26.1 4.6 29 17 41.3 43.4 14.9z"></path>
                                </svg>))}
                            {turn?.cube_owner === 'first' && turn.action !== 'double' && cubeCoords && (
                                <div
                                    style={{
                                        position: 'absolute',
                                        left: cubeCoords.x,
                                        top: cubeCoords.y,
                                        zIndex: 1000,
                                        borderRadius: 8,
                                        background: 'white',
                                        boxShadow: '0 0 4px #aaa',
                                        border: '1px solid gray',
                                        width: 24,
                                        height: 24
                                    }}
                                >
                                    {turn.cube_value}
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="name text-left">{sliceString(data.second.name)}</div>
                    <div className="text-center">Матч до {data.point_match}</div>
                    <div className="name text-right">{sliceString(data.first.name)}</div>
                </div>

                <div className="board">
                    {turn && !turn.dice.includes(0) && (
                        <DiceRoll dice={turn?.dice.length ? turn.dice : [0, 0]}
                                  size={42} className={`dice dice--${turn.turn}`} key={turn.turn}/>
                    )}

                    {turn?.action === 'double' && cubeCoords && (
                        <div
                            style={{
                                position: 'absolute',
                                left: cubeCoords.x,
                                top: cubeCoords.y,
                                zIndex: 1000,
                                borderRadius: 8,
                                background: 'white',
                                boxShadow: '0 0 4px #aaa',
                                border: '1px solid gray',
                                width: 32,
                                height: 32,
                                display: 'flex',
                                justifyContent: 'center',
                                alignItems: 'center',
                                fontSize: 24
                            }}
                        >
                            {turn.cube_value}
                        </div>
                    )}
                    {checkers.map((checker) => (
                        <Checker key={checker.id} {...checker} />
                    ))}
                </div>

                <div className="turns">
                    <div
                        className={`turns-info ${turn?.turn === 'second' && 'turns-info--active'}`}>
                        {turn?.turn === 'second' &&
                            turn.moves.map(({
                                                from,
                                                to,
                                                captured
                                            }, id) => (
                                <span key={id}>{`${from}/${to}${captured ? '*' : ''}`}</span>
                            ))}
                    </div>
                    <div
                        className={`turns-info ${turn?.turn === 'first' && 'turns-info--active'}`}>
                        {turn?.turn === 'first' &&
                            turn.moves.map(({
                                                from,
                                                to,
                                                captured
                                            }, id) => (
                                <span key={id}>{`${from}/${to}${captured ? '*' : ''}`}</span>
                            ))}
                    </div>
                </div>

            </div>

            {data && <div className="bottom-buttons">
                <button
                    onClick={() => {
                        if (gameDirection == -1) {
                            setLastTurn((t) => Math.max(t - 1, -1))
                            setCurrentTurn((t) => Math.max(t - 1, -1));
                        } else {
                            setLastTurn(currentTurn)
                            setGameDirection(-1)
                        }
                    }}
                    className="rounded-md w-full button"
                    data-orientation="left"
                    disabled={isAnimating}
                />
                <span/>
                <button
                    onClick={() => {
                        if (gameDirection == 1) {
                            if (currentTurn === data.turns.length - 1) {
                                setIsGameFinished(true)
                            }
                            setLastTurn(currentTurn)
                            setCurrentTurn((t) => Math.min(t + 1, data.turns.length - 1))
                        } else {
                            setLastTurn((t) => t - 1)
                            setGameDirection(1)
                        }
                    }}
                    className="rounded-md w-full button"
                    data-orientation="right"
                    disabled={isAnimating}
                />
            </div>}
            <div className="flex justify-center">
                <button disabled={screenPending || isAnimating} className="mt-2 rounded-md bg-slate-800 p-2 text-white screen"
                        onClick={handleScreenshot}>
                    {screenPending ? (
                        <span className="loader"></span>
                    ) : (
                        <svg viewBox="0 0 24 24" fill="none"
                             xmlns="http://www.w3.org/2000/svg">
                            <g id="SVGRepo_bgCarrier" strokeWidth="0"></g>
                            <g id="SVGRepo_tracerCarrier" strokeLinecap="round" strokeLinejoin="round"></g>
                            <g id="SVGRepo_iconCarrier">
                                <circle cx="12" cy="13" r="3" stroke="currentColor" strokeWidth="1.5"></circle>
                                <path
                                    d="M2 13.3636C2 10.2994 2 8.76721 2.74902 7.6666C3.07328 7.19014 3.48995 6.78104 3.97524 6.46268C4.69555 5.99013 5.59733 5.82123 6.978 5.76086C7.63685 5.76086 8.20412 5.27068 8.33333 4.63636C8.52715 3.68489 9.37805 3 10.3663 3H13.6337C14.6219 3 15.4728 3.68489 15.6667 4.63636C15.7959 5.27068 16.3631 5.76086 17.022 5.76086C18.4027 5.82123 19.3044 5.99013 20.0248 6.46268C20.51 6.78104 20.9267 7.19014 21.251 7.6666C22 8.76721 22 10.2994 22 13.3636C22 16.4279 22 17.9601 21.251 19.0607C20.9267 19.5371 20.51 19.9462 20.0248 20.2646C18.9038 21 17.3433 21 14.2222 21H9.77778C6.65675 21 5.09624 21 3.97524 20.2646C3.48995 19.9462 3.07328 19.5371 2.74902 19.0607C2.53746 18.7498 2.38566 18.4045 2.27673 18"
                                    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"></path>
                                <path d="M19 10H18" stroke="currentColor" strokeWidth="1.5"
                                      strokeLinecap="round"></path>
                            </g>
                        </svg>
                    )}
                </button>
            </div>
        </div>
    );
}
