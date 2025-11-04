'use client'

import { motion, useAnimation } from 'framer-motion'
import { useEffect, useState } from 'react'
import DiceFace from './DiceFace'

type DiceRollProps = {
    dice: [number, number]
    size?: number
    duration?: number
    notAnimated?: true
    className?: string
}

const getRandomDice = () => (Math.floor(Math.random() * 6) + 1) as 1 | 2 | 3 | 4 | 5 | 6

export default function DiceRoll({
                                     dice,
                                     size = 64,
                                     duration = 0.5,
                                     notAnimated,
                                     className,
                                 }: DiceRollProps) {
    const [rolling, setRolling] = useState(false)
    const [currentDice, setCurrentDice] = useState<[number, number]>([1, 1])
    const [rollKey, setRollKey] = useState(0) // чтобы увеличивать угол при каждом броске

    useEffect(() => {
        if (dice.includes(0) || notAnimated) {
            setCurrentDice(dice)
            setRolling(false)
            return
        }

        setRolling(true)
        let frame = 0
        const interval = setInterval(() => {
            setCurrentDice([getRandomDice(), getRandomDice()])
            frame++
            if (frame > 5) {
                clearInterval(interval)
                setCurrentDice(dice)
                setRolling(false)
                setRollKey(prev => prev + 1) // увеличиваем, чтобы анимация продолжала в ту же сторону
            }
        }, 100)

        return () => clearInterval(interval)
    }, [dice])

    return (
        <div className={`flex gap-4 items-center justify-center ${className}`}>
            {currentDice.map((num, idx) => (
                <AnimatedDie
                    key={idx}
                    rollKey={rollKey}
                    rolling={rolling}
                    duration={duration}
                    size={size}
                    value={num}
                />
            ))}
        </div>
    )
}

function AnimatedDie({
                         rollKey,
                         rolling,
                         duration,
                         value,
                         size,
                     }: {
    rollKey: number
    rolling: boolean
    duration: number
    value: number
    size: number
}) {
    const controls = useAnimation()

    useEffect(() => {
        if (rolling) {
            controls.start({
                rotate: 360 * (rollKey + 1),
                transition: { duration, ease: 'linear' },
            })
        }
    }, [rolling, rollKey])

    return (
        <motion.div animate={controls}>
            <DiceFace value={value} size={size} />
        </motion.div>
    )
}
