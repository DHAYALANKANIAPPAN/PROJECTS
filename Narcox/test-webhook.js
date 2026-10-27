require('dotenv').config();
const webhook = require('./api/telegram/webhook');

const fakeReq = {
  method: 'POST',
  headers: { 'x-telegram-bot-api-secret-token': process.env.TELEGRAM_WEBHOOK_SECRET },
  body: {
    message: {
      chat: { id: -100, title: 'test' },
      from: { id: 1, username: 'seller1' },
      text: 'heroin, mdma cocaine and kanja',
      date: 1700000000
    }
  }
};

const fakeRes = {
  status(code) { console.log('STATUS:', code); return this; },
  json(obj) { console.log('RESPONSE:', obj); },
  send(msg) { console.log('SEND:', msg); }
};

webhook(fakeReq, fakeRes);