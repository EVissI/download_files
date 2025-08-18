import { NextRequest } from 'next/server';
import puppeteer from 'puppeteer';
import { TelegramBotAPI } from '@/lib/telegram';

export async function POST(req: NextRequest) {
    const { state, chat_id } = await req.json();

    if (!state || !chat_id) {
        return new Response(JSON.stringify({ error: 'Missing game state or chat_id' }), { status: 400 });
    }

    const browser = await puppeteer.launch({
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 360, height: 510 });
    const encodedState = encodeURIComponent(JSON.stringify(state));

    await page.goto(`http://localhost:3000/screenshot?state=${encodedState}`, {
        waitUntil: 'networkidle0',
    });

    const fileBytes: Uint8Array = await page.screenshot({ type: 'png' });
    await browser.close();

    const bot = new TelegramBotAPI();
    await bot.sendPhoto({
        chat_id,
        photo: Buffer.from(fileBytes),
        caption: 'Вот текущая позиция на доске 🎲',
    });

    return new Response(JSON.stringify({ ok: true }));
}
