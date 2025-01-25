# -*- coding: utf-8 -*-
import lib.private.ydlfix
import lib.utils as utils
import xbmc
import xbmcaddon
from lib.utils import logger
from lib.youtube_dl import YoutubeDL

lib.private.ydlfix.patch_youtube_dl()

if utils.is_python_3():
    from urllib.parse import unquote
else:
    from urllib import unquote

have_adaptive_plugin = '"enabled":true' in xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.GetAddonDetails","id":1,"params":{"addonid":"inputstream.adaptive", "properties": ["enabled"]}}')
have_youtube_plugin = '"enabled":true' in xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.GetAddonDetails","id":1,"params":{"addonid":"plugin.video.youtube", "properties": ["enabled"]}}')
have_invidious_plugin = '"enabled":true' in xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.GetAddonDetails","id":1,"params":{"addonid":"plugin.video.invidious", "properties": ["enabled"]}}')

def run(argument):
    if argument['type'] == 'magnet':
        handle_magnet(argument['data'])
    elif argument['type'] == 'unresolvedurl':
        if ('queue' not in argument) or (argument['queue'] == 'false'):
            action = 'play'
        else:
            action = 'queue'
        handle_unresolved_url(argument['data'], action)


def handle_magnet(data):
    open_with = utils.get_setting('openMagnetWith')
    logger.info('Sharing magnet with %s' % open_with)
    if open_with == 'Elementum':
        utils.call_plugin('plugin://plugin.video.elementum/playuri?uri=' + data)
    elif open_with == 'Torrenter V2':
        utils.call_plugin('plugin://plugin.video.torrenter/?action=playSTRM&url=' + data)
    elif open_with == 'Quasar':
        utils.call_plugin('plugin://plugin.video.quasar/playuri?uri=' + data)
    elif open_with == 'YATP':
        utils.call_plugin('plugin://plugin.video.yatp/?action=play&torrent=' + data + '&file_index=dialog')


def resolve_with_youtube_dl(url, parameters, action):
    if (utils.get_setting('useCookiesFromBrowser') == 'true'):
        browserName = utils.get_setting('cookiesBrowserName')

        if browserName:
            parameters['cookiesfrombrowser'] = [browserName]

    youtube_dl_resolver = YoutubeDL(parameters)
    youtube_dl_resolver.add_default_info_extractors()
    try:
        result = youtube_dl_resolver.extract_info(url, download=False)
        if result is None:
            result = {}
    except Exception as e:
        logger.error(u'Error with YoutubeDL: %s' % e)
        result = {}
    logger.info(u'YoutubeDL full result: %s' % result)
    if 'entries' in result:
        logger.info(u'Playlist resolved by YoutubeDL: %s items' % len(result['entries']))
        item_list = []
        for entry in result['entries']:
            if entry is not None and 'url' in entry:
                item_list.append(entry)
                logger.info(u'Media found: %s' % entry['url'])
        if len(item_list) > 0:
            utils.play_items(item_list, action)
            return True
        else:
            logger.info(u'No playable urls in the playlist')
    if 'url' in result:
        logger.info(u'Url resolved by YoutubeDL: %s' % result['url'])
        utils.play_url(result['url'], action, result)
        return True
    if 'requested_formats' in result:
        if have_adaptive_plugin:
            logger.info(u'Adaptive plugin enabled looking for dash content')
            for entry in result['requested_formats']:
                if 'container' in entry and 'manifest_url' in entry:
                    if 'dash' in entry['container']:
                        logger.info(u'Url resolved by YoutubeDL: %s' % entry['manifest_url'])
                        utils.play_url(entry['manifest_url'], action, result, True)
                        return True
        for entry in result['requested_formats']:
            if 'protocol' in entry and 'manifest_url' in entry:
                if 'm3u8' in entry['protocol']:
                    logger.info(u'Url resolved by YoutubeDL: %s' % entry['manifest_url'])
                    utils.play_url(entry['manifest_url'], action, result)
                    return True
    return False


def resolve_serienstream(url):
    email = utils.get_setting('stoMail')
    pw = utils.get_setting('stoPW')
    if not email or not pw:
        raise Exception('no login data for s.to provided in settings')
    headers={
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0',
        'Accept-Language': 'de,en-US;q=0.7,en;q=0.3',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate',
        'Upgrade-Insecure-Requests': '1'
    }
    session = requests.Session()
    parts = url.split('/')
    session.post(parts[0] + '//' + parts[2] + '/login', headers=headers, data={'email': email, 'password': pw}).raise_for_status()
    r = session.get(url, headers=headers)
    r.raise_for_status()
    if url == r.url:
        raise Exception('redirect for %s could not be resolved' % url)
    return r.url


def handle_unresolved_url(data, action):
    url = unquote(data)
    logger.info(u'Trying to resolve URL (%s): %s' % (action, url))
    if xbmc.Player().isPlaying():
        utils.show_info_notification(utils.translation(32007), 1000)
    else:
        utils.show_info_notification(utils.translation(32007))
    if 'youtube.com' in url or 'youtu.be' in url:
        if have_youtube_plugin:
            youtube_addon = xbmcaddon.Addon(id="plugin.video.youtube")
            if youtube_addon:
                if utils.get_setting('preferredYoutubeAddon') == "YouTube" or youtube_addon.getSetting("kodion.video.quality.mpd") == "true":
                    logger.info(u'Youtube addon have DASH enabled or is configured as preferred use it')
                    utils.play_url('plugin://plugin.video.youtube/uri2addon/?uri=%s' % data, action)
                    return
        if have_invidious_plugin:
            invidious_addon = xbmcaddon.Addon(id="plugin.video.invidious")
            if invidious_addon:
                if utils.get_setting('preferredYoutubeAddon') == "Invidious":
                    video_id = ""
                    video_id_pos = url.find('v=')
                    if video_id_pos >= 0:
                        video_id = url[video_id_pos + 2:]
                        video_id_pos = video_id.find('&')
                        if video_id_pos >= 0:
                            video_id = video_id[0:video_id_pos]
                    logger.info(u'Playing YouTube video id "%s" with Invidious' % (video_id))
                    utils.play_url('plugin://plugin.video.invidious/?action=play_video&video_id=%s' % video_id, action)
                    return

    if ('://s.to' in url or '://serien.sx' in url or '://serienstream.' in url or '://186.2.175.5/' in url) and '/redirect/' in url:
        xbmc.log(u'resolve serienstream redirect', xbmc.LOGINFO)
        try:
            url = resolve_serienstream(url)
        except Exception as e:
            xbmc.log(u'failure - ' + str(e), xbmc.LOGINFO)
    else:
        media_filter = utils.get_setting('YoutubeDLCustomMediaFilter')
        if utils.get_setting('useYoutubeDLCustomFilter') == 'true' and media_filter:
           logger.info(u'Trying to resolve with YoutubeDL (Preferred YoutubeDL media format filter: %s)' % (media_filter) )
           result = resolve_with_youtube_dl(url, {'format': media_filter, 'no_color': 'true', 'ignoreerrors': 'true'}, action)
        else:
           logger.info(u'Trying to resolve with YoutubeDL (Default Setting)')
           result = resolve_with_youtube_dl(url, {'format': 'best', 'no_color': 'true', 'ignoreerrors': 'true'}, action)
        if result:
           return

    logger.info(u'use resolveurl')
    try:
       import resolveurl
       resolved = resolveurl.resolve(url)
       if resolved:
          utils.play_url(resolved, action)
          return
    except ImportError:
       xbmc.log(u'resolveurl not available', xbmc.LOGINFO)

    xbmc.log(u'Trying to play as basic url', xbmc.LOGINFO)
    utils.play_url(url, action)
    if url:
        utils.show_error_notification(utils.translation(32006))
