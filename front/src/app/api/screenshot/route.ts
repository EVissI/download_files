import { NextRequest } from 'next/server';
import puppeteer from 'puppeteer';
import { TelegramBotAPI } from '@/lib/telegram';

export async function POST(req: NextRequest) {
    console.log('Screenshot API: Starting POST request');
    
    try {
        const { state, chat_id } = await req.json();
        console.log('Screenshot API: Request data received', { state: !!state, chat_id });

        if (!state || !chat_id) {
            console.log('Screenshot API: Missing required data');
            return new Response(JSON.stringify({ error: 'Missing game state or chat_id' }), { status: 400 });
        }

        console.log('Screenshot API: Launching browser');
        const browser = await puppeteer.launch({
            executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium',
            args: ['--no-sandbox', '--disable-setuid-sandbox'],
            headless: true,
        });

        const page = await browser.newPage();
        await page.setViewport({ width: 360, height: 510 });
        
        const encodedState = encodeURIComponent(JSON.stringify(state));
        const screenshotUrl = `http://localhost:3000/screenshot?state=${encodedState}`;
        
        console.log('Screenshot API: Navigating to URL:', screenshotUrl);

        await page.goto(screenshotUrl, {
            waitUntil: 'networkidle0',
            timeout: 30000,
        });

        console.log('Screenshot API: Taking screenshot');
        const fileBytes: Uint8Array = await page.screenshot({ type: 'png' });
        await browser.close();

        console.log('Screenshot API: Sending photo to Telegram');
        const bot = new TelegramBotAPI();
        await bot.sendPhoto({
            chat_id,
            photo: Buffer.from(fileBytes),
        });

        console.log('Screenshot API: Successfully completed');
        return new Response(JSON.stringify({ ok: true }));
        
    } catch (error) {
        console.error('Screenshot API Error:', error);
        return new Response(JSON.stringify({
            error: 'Failed to take screenshot',
            details: error instanceof Error ? error.message : 'Unknown error'
        }), { status: 500 });
    }
}
