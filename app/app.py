import os, requests, json, urllib.parse, urllib.request
from math import sin, cos, acos, radians

from io import BytesIO
from PIL import Image

from IPython import embed
from flask import Flask, request, abort, send_file

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, PostbackEvent, BeaconEvent,
    ImagemapArea, BaseSize,
    TemplateSendMessage, TextMessage, TextSendMessage, ImagemapSendMessage,
    MessageTemplateAction, URITemplateAction, PostbackTemplateAction,URIImagemapAction,
    CarouselTemplate, CarouselColumn, ImageCarouselTemplate, ImageCarouselColumn
)

app = Flask(__name__)
app.config.from_pyfile('./secret.cfg')

line_bot_api = LineBotApi(app.config['ACCESS_TOKEN'])
handler = WebhookHandler(app.config['SECRET_KEY'])

earth_rad = 6378.137

IGNORE_TEXT_LIST = [
    'アイテム',
    'マップ',
]

# Load json data
with open('../data.json') as f:
    STORE_DATA = json.load(f)

@app.route("/imagemap/<path:url>/<size>", methods=['GET'])
def imagemap(url, size):
    print("あああああああああああああああああああ")
    print(url)
    map_image_url = urllib.parse.unquote(url)
    response = requests.get(map_image_url)
    img = Image.open(BytesIO(response.content))
    img_resize = img.resize((int(size), int(size)))
    byte_io = BytesIO()
    img_resize.save(byte_io, 'PNG')
    byte_io.seek(0)
    return send_file(byte_io, mimetype='image/png')


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
    elif is_proper_noun(event.message.text):
        view = carousel_view(event.message.text)
        line_bot_api.reply_message(event.reply_token, view)
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="ん〜〜「%s」は分からないなぁ...\n違う言葉で調べてね!!" % event.message.text))

@handler.add(PostbackEvent)
def handle_postback(event):
    params = {d.split('=')[0]: d.split('=')[1] for d in event.postback.data.split('&')}
    if params['action'] == 'show_items':
        view = handle_posted_postback(params)
        line_bot_api.reply_message(event.reply_token, view)
    elif params['action'] == 'show_maps':
        view = googlemap_imagemap_view(params['text'])
        line_bot_api.reply_message(event.reply_token, view)

def handle_posted_postback(params):
    store = handle_posted_text(params['text'])[int(params['id'])]
    view = image_carousel_view(store['item_images'])
    return view

@handler.add(BeaconEvent)
def handle_beacon(event):
    msg = handle_posted_beacon(event.beacon)
    line_bot_api.reply_message(event.reply_token, msg)

def handle_posted_beacon(data):
    if data.type == "enter":
        print("%sの来客数UP!" % data.hwid)
        msg = TextSendMessage(text="「%s」にようこそ！" % data.hwid)
    else:
        msg = TextSendMessage(text="おおきに〜")
    return msg

def ignore_text(text):
    return text in IGNORE_TEXT_LIST

def is_proper_noun(text):
    api_key = app.config['GOO_API_KEY']
    base_url = "https://labs.goo.ne.jp/api/entity"
    payload = json.dumps({
        "app_id": api_key,
        "sentence": text,
        # ART(人工物名)、ORG(組織名)、PSN(人名)、LOC(地名)
        "class_filter": "ART|ORG|PSN|LOC"
    })

    headers = {
        'content-type': 'application/json'
    }
    req = requests.post(base_url, data=payload, headers=headers)
    result = json.loads(req.text)
    return True if len(result["ne_list"]) > 0 else False

def handle_posted_text(text):
    app.logger.info("Posted text: " + text)
    if text == '清水寺':
        ret = STORE_DATA['kiyomizudera']
    elif text == '伏見稲荷':
        ret = STORE_DATA['hushimiinari']
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
                    data='text=%s&action=show_items&id=%d' % (text, i)
                ),
                PostbackTemplateAction(
                    label='マップ', text='マップ',
                    # data='text=%s&action=show_maps&id=%d' % (d['name'], i)
                    data='text=%s&action=show_maps&id=%d' % (text, i)
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

def googlemap_imagemap_view(text):
    googlemap_geocoding_api_key = app.config['GOOGLE_MAP_API_KEY']
    googlemap_geocoding_base_url = "https://maps.googleapis.com/maps/api/geocode/json?"
    googlemap_geocoding_query = urllib.parse.urlencode({
        "address": text,
        "key": googlemap_geocoding_api_key
    })
    # try:
    req = requests.get(googlemap_geocoding_base_url + googlemap_geocoding_query)
    result = json.loads(req.text)
    lat = result["results"][0]["geometry"]["location"]["lat"]
    lng = result["results"][0]["geometry"]["location"]["lng"]
    googlemap_staticmap_api_key = app.config['GOOGLE_STATIC_MAPS_API_KEY']
    googlemap_staticmap_base_url = "https://maps.googleapis.com/maps/api/staticmap?"
    googlemap_staticmap_query = urllib.parse.urlencode({
        "center": "%s,%s" % (lat, lng),
        "size": "520x520",
        "sensor": "false",
        "scale": 2,
        "maptype": "roadmap",
        "zoom": 18,
        "markers": "%s,%s" % (lat, lng),
        "key": googlemap_staticmap_api_key
    })
    googlemap_staticmap_url = googlemap_staticmap_base_url + googlemap_staticmap_query
    # print(googlemap_staticmap_url)

    # print('https://{}/imagemap/{}'.format(request.host, urllib.parse.quote_plus(googlemap_staticmap_url)))
    view = ImagemapSendMessage(
        base_url = 'https://{}/imagemap/{}'.format(request.host, urllib.parse.quote_plus(googlemap_staticmap_url)),
        alt_text='googlemap',
        base_size=BaseSize(height=1040, width=1040),
        actions=[
            URIImagemapAction(
                link_uri="comgooglemaps://?ll=%f,%f&q=%s" % (lat, lng, text),
                area=ImagemapArea(
                    x=0, y=0, width=1040, height=1040
                )
            )
        ]
    )
    print(view)

    # except:
    #     view = TextSendMessage(text="ん〜〜「%s」はGoogleMapにないなぁ..." % text)

    return view

def latlng_to_xyz(lat, lng):
    rlat, rlng = radians(lat), radians(lng)
    coslat = cos(rlat)
    return coslat*cos(rlng), coslat*sin(rlng), sin(rlat)

def dist_on_sphere(pos0, pos1, radious=earth_rad):
    xyz0, xyz1 = latlng_to_xyz(*pos0), latlng_to_xyz(*pos1)
    return acos(sum(x * y for x, y in zip(xyz0, xyz1)))*radious

if __name__ == "__main__":
    app.run(debug=True)
