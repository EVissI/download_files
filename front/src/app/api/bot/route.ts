'use server'

import {NextRequest, NextResponse} from 'next/server'
import {getNames, parseFile} from '@/lib/parser'
import {mkdirSync} from 'fs'
import path from 'path'
import {randomUUID} from 'crypto'
import {TelegramBotAPI} from "@/lib/telegram";
import {promises as fs} from 'fs';

const miniAppUrl = process.env.MINI_APP_URL;

export async function POST(req: NextRequest) {
    const update = await req.json()
    let chat_id;

    if (update.message) {
        chat_id = update.message.chat.id;
    } else if (update.callback_query) {
        chat_id = update.callback_query.message.chat.id;
    }

    if (!chat_id) {
        // Если нет chat_id, просто возвращаем ошибку
        return NextResponse.json({ ok: false, error: 'No chat_id found' });
    }

    const client = new TelegramBotAPI()

    if (update.message?.text === '/start') {
        await client.sendMessage(
            {chat_id: update.message.chat.id, text: 'Отправьте протокол с игрой в короткие нарды.'}
        )
        return NextResponse.json({ok: true})
    }

    if (update.message?.document) {
        const doc = update.message.document
        const dirName = randomUUID()
        mkdirSync('./tmp', {recursive: true})
        const filePath = path.join('./tmp', dirName);

        await client.sendMessage({
            chat_id,
            text: 'Файл получен. Начинаю обработку...'
        })

        const fileUrl = await client.getFile(doc.file_id)
        const text = await client.downloadFile(fileUrl.file_path)
        await fs.writeFile(filePath, text, 'utf8');

        await client.sendMessage({
                chat_id,
                text: 'Файл обработан. Начинаю подготовку к отображению...'
            }
        );

        const names = await getNames(text);

        const buttons = [[
            {text: `За ${names[0]}`, callback_data: `choose_${filePath}_first`},
            {text: `За ${names[1]}`, callback_data: `choose_${filePath}_second`},
        ]];

        await client.sendMessage({
            chat_id,
            text: `Выбери, за кого просматривать матч:`,
            reply_markup: {inline_keyboard: buttons}
        });
    }

    if (update.callback_query) {
        const chat_id = update.callback_query.message.chat.id;
        const data = update.callback_query.data; // например: choose_{dir}_first
        const dirName = randomUUID()

        const [_, filePath, side] = data.split('_'); // ["choose", "{dir}", "first|second"]

        const text = await fs.readFile(filePath, "utf-8");
        // Парсим
        const games = await parseFile(text, dirName, side === 'second');

        const buttons = [[{
            text: `Открыть игру 📲`,
            web_app: {url: (`${miniAppUrl}?game=${dirName}&chat_id=${chat_id}`)!},
        }]];

        await client.sendMessage({
                chat_id,
                text: 'Готово! Нажми кнопку ниже, чтобы открыть игру и просмотреть ходы.',
                reply_markup: {
                    inline_keyboard: buttons
                }
            }
        )

        return NextResponse.json({ok: true})
    }

    return NextResponse.json({ok: true})
}
