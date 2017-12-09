import os, requests, json, urllib.parse

from IPython import embed
from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, PostbackEvent,
    TemplateSendMessage, TextMessage, TextSendMessage,
    MessageTemplateAction, URITemplateAction, PostbackTemplateAction,
    CarouselTemplate, CarouselColumn, ImageCarouselTemplate, ImageCarouselColumn
)

app = Flask(__name__)
app.config.from_pyfile('./secret.cfg')

line_bot_api = LineBotApi(app.config['ACCESS_TOKEN'])
handler = WebhookHandler(app.config['SECRET_KEY'])

IGNORE_TEXT_LIST = [
    'アイテム',
]

kiyomizu = [
    {
        # 'image': 'http://new-cloudfront.zekkei-japan.jp/images/spots/aflo_AXHA017114.jpg',
        'image': 'https://www.hakuchikudo-original.jp/img/7525kami.jpg',
        'name': '三年坂老舗',
        'description': '扇子売ってるよ',
        'item': 'アイテム',
        'detail': '三年坂老舗の詳細だよーーーー',
        'item_images': [
            'https://www.hakuchikudo-original.jp/img/7525kami.jpg',
            'https://cdn.jalan.jp/jalan/img/6/kuchikomi/2656/KL/cc60c_0002656275_1.jpg',
            # 'http://www.suzukisensu.com/photo/17015/images/v031118-after031118-007-l.jpg',
            'https://cdn.jalan.jp/jalan/img/6/kuchikomi/2656/KL/cc60c_0002656275_1.jpg',
        ],
        'location': {
            'lat': 56.2,
            'lng': 145.9,
        },
    },
    {
        'image': 'https://img.guide.travel.co.jp/article/280/26598/DD84BAB7871E4119B0B20E2EEFE9915E_LL.jpg',
        'name': '八坂老舗',
        'description': '抹茶売ってるよ',
        'item': 'アイテム',
        'detail': '八坂老舗の詳細だよーーーー',
        'item_images': [
            'https://img.guide.travel.co.jp/article/280/26598/DD84BAB7871E4119B0B20E2EEFE9915E_LL.jpg',
            'https://tabetainjya.com/img/1704/tagashirachaho2.jpg',
        ],
        'location': {
            'lat': 56.2,
            'lng': 145.9,
        },
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
    if ignore_text(event.message.text):
        pass
    else:
        view = carousel_view(event.message.text)
        line_bot_api.reply_message(event.reply_token, view)

@handler.add(PostbackEvent)
def handle_postback(event):
    view = handle_posted_postback(event.postback.data)
    line_bot_api.reply_message(event.reply_token, view)

def handle_posted_postback(data):
    params = {d.split('=')[0]: d.split('=')[1] for d in data.split('&')}
    store = kiyomizu[int(params['id'])]
    view = image_carousel_view(store['item_images'])
    return view

def ignore_text(text):
    return text in IGNORE_TEXT_LIST

def handle_posted_text(text):
    app.logger.info("Posted text: " + text)
    if text == '清水寺':
        ret = kiyomizu
    else:
        ret = '見つからなかったよ'

    return ret

def carousel_view(text):
    data = handle_posted_text(text)
    if isinstance(data, str):
        return data

    columns = []
    for i, d in enumerate(data):
        carousel_column = CarouselColumn(
            thumbnail_image_url=d['image'],
            title=d['name'],
            text=d['description'],
            actions=[
                PostbackTemplateAction(
                    label='アイテム', text='アイテム',
                    data='action=show_items&id=%d' % i
                ),
                URITemplateAction(
                    label='詳細',
                    uri='http://example.com/1'
                )
            ]
        )
        columns.append(carousel_column)


    view = TemplateSendMessage(
        alt_text='Carousel template',
        template=CarouselTemplate(columns=columns)
    )
    return view

def image_carousel_view(image_list):
    columns_list = []
    for image in image_list:
        columns_list.append(
            ImageCarouselColumn(
                image_url=image,
                action=URITemplateAction(
                    label='詳細',
                    uri=image
                )
            )
        )

    view = TemplateSendMessage(
        alt_text='ImageCarousel template',
        template=ImageCarouselTemplate(columns=columns_list)
    )
    return view

def googlemap_link(text):
    api_key = app.config['GOOGLE_API_KEY']
    base_url = "https://maps.googleapis.com/maps/api/geocode/json?"
    query = urllib.parse.urlencode({
        "address": text,
        "key": api_key
    })
    url = base_url + query
    try:
        req = requests.get(url)
        result = json.loads(req.text)
        lat = result["results"][0]["geometry"]["location"]["lat"]
        lng = result["results"][0]["geometry"]["location"]["lng"]
        msg = TextSendMessage(text="comgooglemaps://?ll=%f,%f&q=%s" % (lat, lng, text))
    except:
        msg = TextSendMessage(text="申し訳有りません。「%d」は見つかりませんでした。" % text)

    return msg

if __name__ == "__main__":
    app.run(debug=True)
