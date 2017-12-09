import os, requests, json
from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, CarouselTemplate, CarouselColumn,
    MessageTemplateAction, URITemplateAction
)

app = Flask(__name__)
app.config.from_pyfile('./secret.cfg')

line_bot_api = LineBotApi(app.config['ACCESS_TOKEN'])
handler = WebhookHandler(app.config['SECRET_KEY'])

kiyomizu = [
    {
        # 'image': 'http://new-cloudfront.zekkei-japan.jp/images/spots/aflo_AXHA017114.jpg',
        'image': 'https://cdn.jalan.jp/jalan/img/6/kuchikomi/2656/KL/cc60c_0002656275_1.jpg',
        'name': '清水寺',
        'description': '説明',
        'item': 'アイテム',
        'detail': '清水寺の詳細だよーーーー'
    },
    {
        'image': 'https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/Kiyomizu_Temple_-_01.jpg/1200px-Kiyomizu_Temple_-_01.jpg',
        'name': '清水寺2',
        'description': '説明',
        'item': 'アイテム2',
        'detail': '清水寺2の詳細だよーーーー'
    }
]

@app.route("/", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg = carousel_view(event.message.text)
    line_bot_api.reply_message(event.reply_token, msg) # msg)

def handle_posted_text(text):
    app.logger.info("Posted text: " + text)
    ret = kiyomizu

    return ret

def carousel_view(text):
    data = handle_posted_text(text)

    columns = []
    for d in data:
        carousel_column = CarouselColumn(
            thumbnail_image_url=d['image'],
            title=d['name'],
            text=d['description'],
            actions=[
                PostbackTemplateAction(
                    label='アイテム', text='postback text2',
                    data='action=buy&itemid=2'
                ),
                MessageTemplateAction(
                    label='アイテム', text='{}/アイテム'.format(d['name'])
                ),
                URITemplateAction(
                    label='詳細',
                    uri='http://example.com/1'
                )
            ]
        )
        columns.append(carousel_column)


    msg = TemplateSendMessage(
        alt_text='Carousel template',
        template=CarouselTemplate(columns=columns)
    )
    return msg

if __name__ == "__main__":
    app.run(debug=True)
