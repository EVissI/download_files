import React from "react";

type DiceProps = {
    values: number[];
};

export const Dice: React.FC<DiceProps> = ({ values }) => {
    return (
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 flex gap-2 text-white text-xl z-20">
            {values.map((n, i) => (
                <div
                    key={i}
                    className="w-10 h-10 bg-gray-800 rounded flex items-center justify-center border border-white"
                >
                    {n}
                </div>
            ))}
        </div>
    );
};
