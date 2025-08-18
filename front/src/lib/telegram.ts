import fetch from 'node-fetch';
import FormData from 'form-data';

type SendMessageParams = {
    chat_id: number | string;
    text: string;
    parse_mode?: string;
    reply_markup?: object;
};

interface TFile {
    file_id: string;
    file_unique_id: string;
    file_size: number;
    file_path: string;
}

export class TelegramBotAPI {
    private readonly baseUrl: string;

    constructor() {
        this.baseUrl = `https://api.telegram.org/bot${process.env.TELEGRAM_BOT_TOKEN}`;
    }

    // Универсальный запрос к API
    private async apiRequest(method: string, params: any = {}, isMultipart = false) {
        const url = `${this.baseUrl}/${method}`;

        let options: any = {
            method: 'POST',
        };

        if (isMultipart) {
            // Например, при отправке файлов с form-data
            options.body = params; // params - FormData
        } else {
            options.headers = {
                'Content-Type': 'application/json',
            };
            options.body = JSON.stringify(params);
        }

        const res = await fetch(url, options);
        const json = await res.json();

        // @ts-ignore
        if (!json.ok) {
            // @ts-ignore
            throw new Error(`Telegram API error: ${json.description}`);
        }
        // @ts-ignore
        return json.result;
    }

    // Отправить сообщение
    async sendMessage(params: SendMessageParams) {
        return await this.apiRequest('sendMessage', params);
    }

    // Получить путь к файлу
    async getFile(file_id: string): Promise<TFile> {
        return await this.apiRequest('getFile', {file_id});
    }

    // Скачать файл по file_path
    async downloadFile(file_path: string) {
        const fileUrl = `https://api.telegram.org/file/bot${process.env.TELEGRAM_BOT_TOKEN}/${file_path}`;
        const res = await fetch(fileUrl);

        if (!res.ok) {
            throw new Error(`Ошибка, не получилось скачать файл: ${res.statusText}`);
        }

        const contentType = res.headers.get('content-type') || '';

        if (!contentType.startsWith('application')
            && !contentType.startsWith('text')) {
            throw new Error(`Ошибка! Тип файла не соответствует требованиям!`);
        }

        return await res.text();
    }

    // Установить вебхук
    async setWebhook(url: string) {
        return await this.apiRequest('setWebhook', {url});
    }

    // Пример: ответить на inline callback query
    async answerCallbackQuery(callback_query_id: string, text?: string) {
        return await this.apiRequest('answerCallbackQuery', {
            callback_query_id,
            text,
            show_alert: !!text,
        });
    }

    async sendPhoto({
                        chat_id,
                        photo,
                        caption,
                    }: {
        chat_id: number | string;
        photo: Buffer;
        caption?: string;
    }) {
        const form = new FormData();
        form.append('chat_id', chat_id);
        form.append('photo', photo, {
            filename: 'screenshot.png',
            contentType: 'image/png',
        });
        if (caption) form.append('caption', caption);

        return await this.apiRequest('sendPhoto', form, true);
    }

}
