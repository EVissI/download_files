import {JSX} from "react";

type DiceFaceProps = {
    value: number
    size?: number
}

export default function DiceFace({ value, size = 64 }: DiceFaceProps) {
    const r = Math.min(5, size/10)

    const pip = (cx: number, cy: number) => (
        <circle cx={cx} cy={cy} r={r} fill="black" key={`${cx}-${cy}`} />
    )

    const center = size / 2
    const offset = size / 4
    const left = offset
    const right = size - offset
    const top = offset
    const bottom = size - offset

    const positions: Record<number, JSX.Element[]> = {
        0: [],
        1: [pip(center, center)],
        2: [pip(left, top), pip(right, bottom)],
        3: [pip(left, top), pip(center, center), pip(right, bottom)],
        4: [pip(left, top), pip(right, top), pip(left, bottom), pip(right, bottom)],
        5: [pip(left, top), pip(right, top), pip(center, center), pip(left, bottom), pip(right, bottom)],
        6: [pip(left, top), pip(right, top), pip(left, center), pip(right, center), pip(left, bottom), pip(right, bottom)],
    }

    return (
        <svg
            width={size}
            height={size}
            viewBox={`0 0 ${size} ${size}`}
            style={{ borderRadius: 8, background: 'white', boxShadow: '0 0 4px #aaa', border: '1px solid gray' }}
        >
            {positions[value]}
        </svg>
    )
}
