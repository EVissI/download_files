'use client';
import {FC, Suspense, useEffect, useState} from "react";
import {useSearchParams} from "next/navigation";
import {GameData} from "@/components/types";
import Board from "@/components/Board";

export const Games: FC = () => {
    const params = useSearchParams();
    const dirName = params.get('game');
    const [games, setGames] = useState<GameData[] | null>(null);
    const [currentGameIndex, setCurrentGameIndex] = useState<number>(0);
    console.log("%c 1 --> Line: 12||Games.tsx\n currentGameIndex: ", "color:#f0f;", currentGameIndex);
    const [isGameFinished, setIsGameFinished] = useState<boolean>(false);
    const [isMenuOpened, setIsMenuOpened] = useState<boolean>(false);
    const game = games ? games[currentGameIndex] : undefined;
    console.log("%c 2 --> Line: 16||Games.tsx\n games: ", "color:#0f0;", games);
    console.log("%c 3 --> Line: 16||Games.tsx\n game: ", "color:#ff0;", game);

    useEffect(() => {
        fetch(`/json/${dirName}/games.json`)
            .then((res) => res.json())
            .then(setGames);
    }, []);

    const handleNextGame = (from: string) => {
        console.log("%c 6 --> Line: 26||Games.tsx\n from: ", "color:#00f;", from);
        if (!games) return;
        if (currentGameIndex < games.length - 1) {
            setCurrentGameIndex((t) => t + 1);
            setIsGameFinished(false);
        }
    };

    if (!games) {
        return (
            <div className="min-h-screen flex justify-center items-center">
                <span className="loader"></span>
            </div>
        );
    }

    return (
        <div className="relative">
            <Board key={currentGameIndex} gameData={game} setIsGameFinished={(a) => {
                setIsGameFinished(a)
                console.log("%c 7 --> Line: 46||Games.tsx\n setIsGameFinished: ", "color:#acf;", setIsGameFinished);
            }}
                   chatId={params.get('chat_id')}/>

            <div className="menu-container">
                {isMenuOpened ?
                    <button
                        onClick={() => setIsMenuOpened(false)}
                        className="rounded-md border border-slate-300 py-1 px-2 text-center text-xs transition-all shadow-xs hover:shadow-lg text-slate-600 hover:text-white hover:bg-slate-800 hover:border-slate-800 focus:text-white focus:bg-slate-800 focus:border-slate-800 active:border-slate-800 active:text-white active:bg-slate-800 disabled:pointer-events-none disabled:opacity-50 disabled:shadow-none"
                    >
                        Игра
                    </button>
                    :
                    <>
                        <button
                            onClick={() => setIsMenuOpened(true)}
                            className="rounded-md border border-slate-300 py-1 px-2 text-center text-xs transition-all shadow-xs hover:shadow-lg text-slate-600 hover:text-white hover:bg-slate-800 hover:border-slate-800 focus:text-white focus:bg-slate-800 focus:border-slate-800 active:border-slate-800 active:text-white active:bg-slate-800 disabled:pointer-events-none disabled:opacity-50 disabled:shadow-none"
                        >
                            Меню
                        </button>
                        <div
                            className="text-xs"
                        >
                            Игра {currentGameIndex + 1}
                        </div>
                    </>
                }
            </div>

            {isGameFinished && (
                <div
                    className="absolute inset-0 opacity-60 flex flex-col justify-center items-center text-center z-50 cursor-pointer"
                    onClick={() => handleNextGame('handleNextGame')}
                    style={{backgroundColor: '#fff8e7'}}
                >
                    <div className="text-3xl font-bold mb-4">Игра завершена</div>
                    <div className="text-lg">Нажмите в любом месте, чтобы перейти к следующей</div>
                </div>
            )}
            {isMenuOpened && (
                <div
                    className="absolute inset-0 opacity-90 z-50 cursor-pointer overflow-scroll pt-8"
                    style={{backgroundColor: '#fff8e7'}}
                >
                    <div className=" gap-4 flex flex-col justify-center items-center text-center">
                        <div
                            className="text-3xl font-bold mb-4"
                        >Выберите игру:
                        </div>
                        {games.map((_, index) => (
                            <button
                                onClick={() => {
                                    setCurrentGameIndex(index);
                                    setIsMenuOpened(false);
                                }}
                                key={index}
                                className="rounded-md bg-gradient-to-tr from-slate-800 to-slate-700 py-2 px-4 border border-transparent text-center text-sm text-white transition-all shadow-md hover:shadow-lg focus:bg-slate-700 focus:shadow-none active:bg-slate-700 hover:bg-slate-700 active:shadow-none disabled:pointer-events-none disabled:opacity-50 disabled:shadow-none"
                            >
                                Игра {index + 1}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export const GamesClient = () => (
    <Suspense fallback={<div>Загрузка...</div>}>
        <Games/>
    </Suspense>
)