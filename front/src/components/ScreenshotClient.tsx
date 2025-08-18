'use client';
import {useEffect, useState, Suspense} from 'react';
import {useSearchParams} from 'next/navigation';
import {CheckerData, PlayerInfo, Turn} from "@/components/types";
import {getCubeCoords, sliceString} from "@/lib/helpers";
import {Checker} from "@/components/Checker";
import DiceRoll from "@/components/DiceRoll";

interface state {
    checkers: CheckerData[];
    first: PlayerInfo;
    point_match: number;
    second: PlayerInfo;
    currentTurn: Turn;
}

export default function InnerScreenshotClient() {
    const searchParams = useSearchParams();
    const [state, setState] = useState<state | null>(null);
    const turn = state?.currentTurn;
    const cubeCoords = turn ? getCubeCoords(turn.cube_location) : null;

    useEffect(() => {
        const stateParam = searchParams.get('state');
        if (!stateParam) return;

        const state = JSON.parse(decodeURIComponent(stateParam));
        setState(state);
    }, [searchParams]);

    if (!state) return <></>;

    return (
        <div style={{backgroundColor: '#fff8e7'}} className='p-2'>
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
                    <div className="score">{state.second.score}</div>
                </div>
                <div className="font-sans p-2 text-lg">:</div>
                <div className="header_item justify-end">
                    <div className="score">{state.first.score}</div>
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
                <div className="name text-left">{sliceString(state.second.name)}</div>
                <div className="text-center">Матч до {state.point_match}</div>
                <div className="name text-right">{sliceString(state.first.name)}</div>
            </div>

            <div className="board">
                {turn && !turn.dice.includes(0) && (
                    <DiceRoll dice={turn?.dice.length ? turn.dice : [0, 0]}
                              size={42} className={`dice dice--${turn.turn}`} key={turn.turn} notAnimated/>
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
                {state.checkers.map((checker) => (
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
    );
}

export const ScreenshotClient = () => (
    <Suspense fallback={<div>Загрузка...</div>}>
        <InnerScreenshotClient/>
    </Suspense>
)