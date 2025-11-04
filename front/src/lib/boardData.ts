export const CHECKER_RADIUS = 60;
export const IMAGE_WIDTH = 1156;

// Исходные точки для координат
const START_X_1 = 128;
const START_X_2 = 615;
const X_SPACE = 70;

const START_Y_1 = 975;
const START_Y_2 = 40;

export const ZERO_COORDS = {
    first: {x: 1065, y: START_Y_1},
    second: {x: 30, y: START_Y_2},
}

// Центры точек (24 позиции)
export const POINT_COORDS: Record<string, { x: number; y: number }> = {
    "1": {x: START_X_2 + X_SPACE * 5, y: START_Y_1},
    "2": {x: START_X_2 + X_SPACE * 4, y: START_Y_1},
    "3": {x: START_X_2 + X_SPACE * 3, y: START_Y_1},
    "4": {x: START_X_2 + X_SPACE * 2, y: START_Y_1},
    "5": {x: START_X_2 + X_SPACE, y: START_Y_1},
    "6": {x: START_X_2, y: START_Y_1},
    "7": {x: START_X_1 + X_SPACE * 5, y: START_Y_1},
    "8": {x: START_X_1 + X_SPACE * 4, y: START_Y_1},
    "9": {x: START_X_1 + X_SPACE * 3, y: START_Y_1},
    "10": {x: START_X_1 + X_SPACE * 2, y: START_Y_1},
    "11": {x: START_X_1 + X_SPACE, y: START_Y_1},
    "12": {x: START_X_1, y: START_Y_1},
    "13": {x: START_X_1, y: START_Y_2},
    "14": {x: START_X_1 + X_SPACE, y: START_Y_2},
    "15": {x: START_X_1 + X_SPACE * 2, y: START_Y_2},
    "16": {x: START_X_1 + X_SPACE * 3, y: START_Y_2},
    "17": {x: START_X_1 + X_SPACE * 4, y: START_Y_2},
    "18": {x: START_X_1 + X_SPACE * 5, y: START_Y_2},
    "19": {x: START_X_2, y: START_Y_2},
    "20": {x: START_X_2 + X_SPACE, y: START_Y_2},
    "21": {x: START_X_2 + X_SPACE * 2, y: START_Y_2},
    "22": {x: START_X_2 + X_SPACE * 3, y: START_Y_2},
    "23": {x: START_X_2 + X_SPACE * 4, y: START_Y_2},
    "24": {x: START_X_2 + X_SPACE * 5, y: START_Y_2},
};

// Бар — координаты центра бара для каждого игрока
export const BAR_COORDS: Record<"first" | "second", { x: number; y: number }> = {
    first: {x: 547, y: 447},
    second: {x: 547, y: 567}
};

// Направления отрисовки шашек
export const DIRECTION: Record<"first" | "second", 1 | -1> = {
    first: -1,
    second: 1
};

export const DEFAULT_CHECKERS = {
    'first': {
        'Bar': 0,
        '0': 0,
        '1': 0,
        '2': 0,
        '3': 0,
        '4': 0,
        '5': 0,
        '6': 5,
        '7': 0,
        '8': 3,
        '9': 0,
        '10': 0,
        '11': 0,
        '12': 0,
        '13': 5,
        '14': 0,
        '15': 0,
        '16': 0,
        '17': 0,
        '18': 0,
        '19': 0,
        '20': 0,
        '21': 0,
        '22': 0,
        '23': 2,
        '24': 1,
    },
    'second': {
        'Bar': 0,
        '0': 0,
        '1': 0,
        '2': 0,
        '3': 0,
        '4': 0,
        '5': 0,
        '6': 5,
        '7': 0,
        '8': 3,
        '9': 0,
        '10': 0,
        '11': 0,
        '12': 0,
        '13': 5,
        '14': 0,
        '15': 0,
        '16': 0,
        '17': 0,
        '18': 0,
        '19': 0,
        '20': 0,
        '21': 0,
        '22': 0,
        '23': 2,
        '24': 1,
    }
}

export const SHORT_DEFAULT_CHECKERS = {
    'first': {
        'Bar': 0,
        '0': 0,
        '1': 0,
        '2': 0,
        '3': 0,
        '4': 0,
        '5': 0,
        '6': 5,
        '7': 0,
        '8': 3,
        '9': 0,
        '10': 0,
        '11': 0,
        '12': 0,
        '13': 5,
        '14': 0,
        '15': 0,
        '16': 0,
        '17': 0,
        '18': 0,
        '19': 0,
        '20': 0,
        '21': 0,
        '22': 0,
        '23': 0,
        '24': 2,
    },
    'second': {
        'Bar': 0,
        '0': 0,
        '1': 0,
        '2': 0,
        '3': 0,
        '4': 0,
        '5': 0,
        '6': 5,
        '7': 0,
        '8': 3,
        '9': 0,
        '10': 0,
        '11': 0,
        '12': 0,
        '13': 5,
        '14': 0,
        '15': 0,
        '16': 0,
        '17': 0,
        '18': 0,
        '19': 0,
        '20': 0,
        '21': 0,
        '22': 0,
        '23': 0,
        '24': 2,
    }
}