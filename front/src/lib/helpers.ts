import {Player} from "@/components/types";
import {
    BAR_COORDS,
    CHECKER_RADIUS,
    DEFAULT_CHECKERS,
    DIRECTION,
    POINT_COORDS,
    SHORT_DEFAULT_CHECKERS,
    ZERO_COORDS
} from "@/lib/boardData";

export const togglePlayer = (player: Player): Player => {
    return player === 'first' ? 'second' : 'first';
}

export const getRealPoint = (point: string, player: Player): string => {
    if (player === "second" && point !== "Bar") return String((25 - Number(point)) % 25);
    return point;
}

export const getDirection = (point: string, player: Player) => {
    if (point === "Bar" || point === '0') return DIRECTION[player];
    if (Number(point) < 13) return -1;
    return 1;
}

export const calculateCordY = (y: number, index: number, direction: number, point: string): number => {
    const space = point === 'Bar' ? 0.5 : point === '0' ? 1.03 : 1.1;
    return y + index * direction * (CHECKER_RADIUS * space)
}

export const generateDefaultCheckersData = (isLongGame?: boolean) => {
    const checkers = [];
    const defaultCheckers = isLongGame ? DEFAULT_CHECKERS : SHORT_DEFAULT_CHECKERS;
    let idCounters: Record<Player, number> = {first: 0, second: 0};
    for (const player of ["first", "second"] as Player[]) {
        const entries = Object.entries(defaultCheckers[player]).filter(
            ([key]) => key === "Bar" || /^[0-9]+$/.test(key)
        );

        for (const [point, count] of entries) {
            const n = Number(count);
            let realPoint = getRealPoint(point, player);
            let direction = getDirection(realPoint, player);

            const {
                x,
                y
            } = realPoint === "Bar" ? BAR_COORDS[player] : realPoint === "0" ? ZERO_COORDS[player] : POINT_COORDS[realPoint];
            const distanceFromCenter = Math.abs(12.5 - Number(realPoint));

            for (let i = 0; i < n; i++) {
                checkers.push({
                    id: `${player}-${idCounters[player]++}`,
                    player,
                    index: i,
                    x,
                    y: calculateCordY(y, i, direction, realPoint),
                    direction,
                    sortOrder: distanceFromCenter + i * 0.1,
                    currentPosition: realPoint,
                    check: false,
                });
            }
        }
    }
    return checkers;
}

export const sliceString = (str: string): string => {
    if (str.length < 12) return str;
    return `${str.slice(0, 8)}...${str.slice(str.length - 2)}`;
}

export function getCubeCoords(cubeLocation: 'center' | Player | null) {
    if (cubeLocation === 'center') {
        return {x: 'calc(50% - 16px)', y: 'calc(50% - 16px)'}; // пример координат центра доски
    }
    if (cubeLocation === 'first') {
        return {x: '60%', y: '60%'}; // рядом с первым игроком
    }
    if (cubeLocation === 'second') {
        return {x: '60%', y: '60%'}; // рядом со вторым игроком
    }
    return null;
}
