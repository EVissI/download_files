'use client'

import {motion} from 'framer-motion'
import {useEffect, useState} from 'react'
import DiceFace from './DiceFace'

type DiceRollProps = {
    dice: [number, number]
    size?: number
    duration?: number;
    notAnimated?: true;
    className?: string;
}

const getRandomDice = () => Math.floor(Math.random() * 6) + 1 as 1 | 2 | 3 | 4 | 5 | 6

export default function DiceRoll({dice, size = 64, notAnimated, className}: DiceRollProps) {
    const [rolling, setRolling] = useState(true)
    const [currentDice, setCurrentDice] = useState<[number, number]>([1, 1])

    useEffect(() => {
        if (dice.includes(0) || notAnimated) {
            setCurrentDice(dice)
            setRolling(false)
            return;
        }
        let frame = 0
        const interval = setInterval(() => {
            setCurrentDice([getRandomDice(), getRandomDice()])
            frame++
            if (frame > 5) {
                clearInterval(interval)
                setCurrentDice(dice)
                setRolling(false)
            }
        }, 100)

        return () => clearInterval(interval)
    }, [dice])

    return (
        <div className={`flex gap-4 items-center justify-center ${className}`}>
            {currentDice.map((num, idx) => (
                <motion.div
                    key={idx}
                    initial={{rotate: 0}}
                    animate={{rotate: rolling ? 360 : 0}}
                    transition={{duration: 0.5}}
                >
                    <DiceFace value={num} size={size}/>
                </motion.div>
            ))}
        </div>
    )
}
