import os, requests, json, urllib.parse
from math import sin, cos, acos, radians

from IPython import embed
from flask import Flask, request, abort
from flaskext.mysql import MySQL

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, PostbackEvent, BeaconEvent,
    TemplateSendMessage, TextMessage, TextSendMessage,
    MessageTemplateAction, URITemplateAction, PostbackTemplateAction,
    CarouselTemplate, CarouselColumn, ImageCarouselTemplate, ImageCarouselColumn
)

app = Flask(__name__)
app.config.from_pyfile('./secret.cfg')

mysql = MySQL()
# MySQL configurations
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_DB'] = 'resas2017'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
mysql.init_app(app)
conn = mysql.connect()
cursor = conn.cursor()

line_bot_api = LineBotApi(app.config['ACCESS_TOKEN'])
handler = WebhookHandler(app.config['SECRET_KEY'])

earth_rad = 6378.137

IGNORE_TEXT_LIST = [
    'アイテム'
]

INGORE_START_WITH = [
    '店舗の詳細\n'
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

def handle_posted_postback(params):
    store = handle_posted_text(params['text'])[int(params['id'])]
    store_id, name, thumbnail, description, detail, lat, lng, beacon_id, visitor_count = store
    items = get_items_from_db(store_id)
    view = image_carousel_view(items)
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
    flag = text in IGNORE_TEXT_LIST
    if flag:
        return flag
    else:
        for t in INGORE_START_WITH:
            if text.startswith(t):
                return True
        else:
            return False

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
    ret = get_stores_from_db(text)
    if not ret:
        ret = TextSendMessage(text='見つからなかったよ')
    return ret

def carousel_view(text):
    data = handle_posted_text(text)
    if isinstance(data, TextSendMessage):
        return data

    columns = []
    for i, d in enumerate(data):
        store_id, name, thumbnail, description, detail, lat, lng, beacon_id, visitor_count = d
        carousel_column = CarouselColumn(
            thumbnail_image_url=thumbnail,
            title=name,
            text=description,
            actions=[
                PostbackTemplateAction(
                    label='アイテム', text='アイテム',
                    data='text=%s&action=show_items&id=%d' % (text, i)
                ),
                MessageTemplateAction(
                    label='詳細',
                    text="店舗の詳細\n"+detail
                )
            ]
        )
        columns.append(carousel_column)


    view = TemplateSendMessage(
        alt_text='老舗の一覧',
        template=CarouselTemplate(columns=columns)
    )
    return view

def image_carousel_view(image_list):
    columns_list = []
    for image, label in image_list:
        columns_list.append(
            ImageCarouselColumn(
                image_url=image,
                action=URITemplateAction(
                    label=label,
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
        msg = TextSendMessage(text="申し訳有りません。「%s」は見つかりませんでした。" % text)

    return msg

def latlng_to_xyz(lat, lng):
    rlat, rlng = radians(lat), radians(lng)
    coslat = cos(rlat)
    return coslat*cos(rlng), coslat*sin(rlng), sin(rlat)

def dist_on_sphere(pos0, pos1, radious=earth_rad):
    xyz0, xyz1 = latlng_to_xyz(*pos0), latlng_to_xyz(*pos1)
    return acos(sum(x * y for x, y in zip(xyz0, xyz1)))*radious

def get_stores_from_db(keyword):
    sql = """
select
  *
from
  stores
where id in (
  select
    store_id
  from
    keyword_relationships
  where
    keyword_id in (
        select
        id
      from
        keywords
      where
        keyword = '{}'
    )
  )
;
    """.format(keyword)

    cursor.execute(sql)
    ret = cursor.fetchall()
    return ret

def get_items_from_db(store_id):
    sql = """
select
  url, label
from
  items
where
  store_id = {}
;
    """.format(store_id)

    cursor.execute(sql)
    ret = cursor.fetchall()
    return ret

if __name__ == "__main__":
    app.run(debug=True)
