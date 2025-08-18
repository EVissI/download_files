import {motion} from "framer-motion";
import {CHECKER_RADIUS, IMAGE_WIDTH} from "@/lib/boardData";

type Player = "first" | "second";

type CheckerProps = {
    id: string;
    player: Player;
    x: number;
    y: number;
    delay?: number;
    check: boolean;
};

export const Checker: React.FC<CheckerProps> = ({x, y, player, id, delay, check}) => {
    const xPercent = (x / IMAGE_WIDTH) * 100;
    const yPercent = (y / 1086) * 100;
    const width = (CHECKER_RADIUS / IMAGE_WIDTH) * 100;

    return (
        <motion.div
            layoutId={id}
            initial={false}
            animate={{
                left: `${xPercent}%`,
                top: `${yPercent}%`,
            }}
            transition={{duration: 0.4, ease: "easeInOut", delay}}
            className={`checker checker--${player} ${check && 'checker--check'}`}
            style={{
                position: "absolute",
                width: `${width}%`,
            }}
            data-id={id}
        />
    );
};

