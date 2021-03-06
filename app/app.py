import os, requests, json, urllib.parse, urllib.request
from math import sin, cos, acos, radians

from io import BytesIO
from PIL import Image

import numpy as np
import math

from IPython import embed
from flask import Flask, request, abort, send_file
from flaskext.mysql import MySQL

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, PostbackEvent, BeaconEvent,
    ImagemapArea, BaseSize,
    TemplateSendMessage, TextMessage, TextSendMessage, ImagemapSendMessage, LocationMessage,
    MessageTemplateAction, URITemplateAction, PostbackTemplateAction,URIImagemapAction, MessageImagemapAction,
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
offset = 268435456;
radius = offset / np.pi;

REGISTERED_TEXT_LIST = [
    '使い方',
    'キーワードリスト'
]

REGISTERED_START_WITH = [
    '店舗名：',
]

IGNORE_TEXT_LIST = [
    'アイテム',
    'マップ',
]

INGORE_START_WITH = [
    '店舗の詳細\n',
]

USAGE_TEXT = """
こんにちは、うちの老舗（どすえ）案内人の「しにりん」やで(*^^*)
あなたの知りたい事柄に合った京都の老舗について案内するよ。
検索方法は、「キーワードリストから検索」と「現在地から検索」の２通りあるよ。

「キーワードリストから検索」では、気になるキーワードを入力すると、それに合った老舗情報が一覧表示されるよ。
「現在地から検索する」場合は、マップ上に老舗が表示されるので、タッチすると情報が表示されるよ。
気になる老舗が合ったらぜひ、訪れてみてね！　
""".strip()

NOTFOUND_MESSAGE = """
入力したキーワードに関連する老舗は見つからへんなあ(´Д｀)
別のキーワードを入力してみてね！
""".strip()

FOUND_MESSAGE = """
お探しの老舗情報が見つかったで（＾▽＾)ノ
詳しくは、「アイテム」もしくは「詳細」をタッチしてね♪
""".strip()

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

@app.route("/imagemap/<path:url>/<size>", methods=['GET'])
def imagemap(url, size):
    map_image_url = urllib.parse.unquote(url)
    response = requests.get(map_image_url)
    img = Image.open(BytesIO(response.content))
    img_resize = img.resize((int(size), int(size)))
    byte_io = BytesIO()
    img_resize.save(byte_io, 'PNG')
    byte_io.seek(0)
    return send_file(byte_io, mimetype='image/png')

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text
    if regitered_text(text):
        view = handle_registered_text(text)
        line_bot_api.reply_message(event.reply_token, view)
    elif ignore_text(text):
        pass
    elif is_proper_noun(text):
        view = carousel_view(text)
        line_bot_api.reply_message(
            event.reply_token,
            [TextSendMessage(text=FOUND_MESSAGE), view]
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=NOTFOUND_MESSAGE)
        )

@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    lat = event.message.latitude
    lng = event.message.longitude
    location = "あなたの位置情報\n緯度x経度 = {}x{}".format(lat, lng)

    sql = """
select
	name, lat, lng
from
	stores
;
    """

    cursor.execute(sql)
    stores = cursor.fetchall()
    self_locate_maker = '&markers=color:{}|label:{}|{},{}'.format('blue', '', lat, lng)
    center_lat_pixel, center_lon_pixel = latlon_to_pixel(lat, lng)

    zoomlevel = 15
    imagesize = 1040
    marker_color = 'blue';
    label = 'S';

    pin_width = 60 * 1.5;
    pin_height = 84 * 1.5;

    actions = []
    self_locate_maker = ''

    for i, store in enumerate(stores):
        self_locate = lat, lng
        store_locate = store[1], store[2]
        dist = dist_on_sphere(self_locate, store_locate)
        # 1km以内
        if dist < 1:
            print(dist)
            # 中心の緯度経度をピクセルに変換
            target_lat_pixel, target_lon_pixel = latlon_to_pixel(store[1], store[2])

            # 差分を計算
            delta_lat_pixel  = (target_lat_pixel - center_lat_pixel) >> (21 - zoomlevel - 1);
            delta_lon_pixel  = (target_lon_pixel - center_lon_pixel) >> (21 - zoomlevel - 1);

            marker_lat_pixel = imagesize / 2 + delta_lat_pixel;
            marker_lon_pixel = imagesize / 2 + delta_lon_pixel;

            x = marker_lat_pixel
            y = marker_lon_pixel

            # 範囲外のを除外
            if(pin_width / 2 < x < imagesize - pin_width / 2 and pin_height < y < imagesize - pin_width):

                self_locate_maker += '&markers=color:{}|label:{}|{},{}'.format(marker_color, label, store[1], store[2])

                actions.append(MessageImagemapAction(
                    text = "店舗名：" + str(store[0]),
                    area = ImagemapArea(
                        x = x - pin_width / 2,
                        y = y - pin_height / 2,
                        width = pin_width,
                        height = pin_height
                    )
                ))

    googlemap_staticmap_api_key = app.config['GOOGLE_STATIC_MAPS_API_KEY']
    googlemap_staticmap_base_url = "https://maps.googleapis.com/maps/api/staticmap?"
    googlemap_staticmap_query = urllib.parse.urlencode({
        "center": "%s,%s" % (lat, lng),
        "size": "520x520",
        "sensor": "false",
        "scale": 2,
        "maptype": "roadmap",
        "zoom": zoomlevel,
        "markers": "%s,%s" % (lat, lng),
        "key": googlemap_staticmap_api_key
    })
    googlemap_staticmap_url = googlemap_staticmap_base_url + googlemap_staticmap_query + self_locate_maker + self_locate_maker
    view = ImagemapSendMessage(
        base_url = 'https://{}/imagemap/{}'.format(request.host, urllib.parse.quote_plus(googlemap_staticmap_url)),
        alt_text='googlemap',
        base_size=BaseSize(height=imagesize, width=imagesize),
        actions=actions
    )

    if len(actions) > 0:
        msg = "ここの近くにはこんな老舗があるよ！"
    else:
        msg = "ん〜ここの近くには何もないなぁ"

    line_bot_api.reply_message(event.reply_token,
        [
            view,
            TextSendMessage(text=msg)
        ]
    )

def latlon_to_pixel(lat, lon):
    lat_pixel = round(offset + radius * lon * np.pi / 180);
    lon_pixel = round(offset - radius * math.log((1 + math.sin(lat * np.pi / 180)) / (1 - math.sin(lat * np.pi / 180))) / 2);
    return lat_pixel, lon_pixel

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
    store = get_store_by_name(params['name'])
    store_id, name, thumbnail, description, detail, lat, lng, beacon_id, visitor_count = store
    items = get_items_from_db(store_id)
    view = image_carousel_view(items)
    return view

def handle_registered_text(text):
    if text == '使い方':
        view = TextSendMessage(text=USAGE_TEXT)
    elif text == 'キーワードリスト':
        sql = """
select
	keyword
from
	keywords
order by
	rand()
limit 10
;
        """
        cursor.execute(sql)
        ret = '\n'.join([d[0] for d in cursor.fetchall()]).strip()
        view = TextSendMessage(text="現在登録されているキーワードの例\n"+ret)
    elif text.startswith("店舗名："):
        store_name = text.replace("店舗名：", "")
        store = get_store_by_name(store_name)
        view = TemplateSendMessage(
            alt_text=store_name,
            template=CarouselTemplate(columns=[create_carousel_column(store)])
        )
    else:
        raise "Not registered text"
    return view

@handler.add(BeaconEvent)
def handle_beacon(event):
    msg = handle_posted_beacon(event.beacon)
    line_bot_api.reply_message(event.reply_token, msg)

def handle_posted_beacon(data):
    if data.type == "enter":
        print("%sの来客数UP!" % data.hwid)
        ret = cursor.execute('select * from stores where beacon_id = "{}";'.format(data.hwid))
        if ret:
            store_name = cursor.fetchall()[0][1]
            cursor.execute('update stores set visitor_count = visitor_count + 1 where beacon_id = "{}";'.format(data.hwid))
            msg = TextSendMessage(text="「%s」にようこそ！" % store_name)
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

def regitered_text(text):
    flag = text in REGISTERED_TEXT_LIST
    if flag:
        return flag
    else:
        for t in REGISTERED_START_WITH:
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
        ret = TextSendMessage(text='NOTFOUND_MESSAGE')
    return ret

def carousel_view(text):
    data = handle_posted_text(text)
    if isinstance(data, TextSendMessage):
        return data

    columns = []
    for i, d in enumerate(data):
        carousel_column = create_carousel_column(d)
        columns.append(carousel_column)

    view = TemplateSendMessage(
        alt_text='老舗の一覧',
        template=CarouselTemplate(columns=columns)
    )
    return view

def create_carousel_column(store):
    store_id, name, thumbnail, description, detail, lat, lng, beacon_id, visitor_count = store
    carousel_column = CarouselColumn(
        thumbnail_image_url=thumbnail,
        title=name,
        text=description,
        actions=[
            PostbackTemplateAction(
                label='アイテム', text='アイテム',
                data='name=%s&action=show_items' % (name)
            ),
            PostbackTemplateAction(
                label='マップ', text='マップ',
                data='text=%s&action=show_maps' % (name)
            ),
            MessageTemplateAction(
                label='詳細',
                text="店舗の詳細\n"+detail
            )
        ]
    )
    return carousel_column

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

def googlemap_imagemap_view(text):
    googlemap_geocoding_api_key = app.config['GOOGLE_MAP_API_KEY']
    googlemap_geocoding_base_url = "https://maps.googleapis.com/maps/api/geocode/json?"
    googlemap_geocoding_query = urllib.parse.urlencode({
        "address": text,
        "key": googlemap_geocoding_api_key
    })
    try:
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

        view = ImagemapSendMessage(
            base_url = 'https://{}/imagemap/{}'.format(request.host, urllib.parse.quote_plus(googlemap_staticmap_url)),
            alt_text='googlemap',
            base_size=BaseSize(height=1040, width=1040),
            actions=[
                URIImagemapAction(
                    # link_uri='comgooglemaps://?ll=%f,%f&q=%s' % (lat, lng, text),
                    link_uri='http://maps.google.co.jp/maps?q=%f,%f' % (lat, lng),
                    area=ImagemapArea(
                        x=0, y=0, width=1040, height=1040
                    )
                )
            ]
        )

    except:
        view = TextSendMessage(text="ん〜〜「%s」はGoogleMapにないなぁ..." % text)

    return view

def latlng_to_xyz(lat, lng):
    rlat, rlng = radians(lat), radians(lng)
    coslat = cos(rlat)
    return coslat*cos(rlng), coslat*sin(rlng), sin(rlat)

def dist_on_sphere(pos0, pos1, radious=earth_rad):
    xyz0, xyz1 = latlng_to_xyz(*pos0), latlng_to_xyz(*pos1)
    return acos(sum(x * y for x, y in zip(xyz0, xyz1)))*radious

def get_store_by_name(name):
    sql = """
select
	*
from
	stores
where
    name = "{}"
;
    """.format(name)
    cursor.execute(sql)
    store = cursor.fetchall()[0]
    return store

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
