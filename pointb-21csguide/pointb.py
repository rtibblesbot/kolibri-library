import pprint
import youtube_dl


class PointBVideo():

    uid = 0   # value from `id` after `youtube_dl.extract_info()`
    title = ''
    description = ''
    url = ''
    lang_code = ''
    filename_prefix = ''

    def __init__(self, uid=0, url='', title='', description='', lang_code='', 
            filename_prefix=''):
        self.uid = uid
        self.url = url
        self.title = title
        self.description = description
        self.lang_code = lang_code
        self.filename_prefix = filename_prefix
        print(self)

    def __str__(self):
        return 'PointBVideo (%s - %s - %s - %s)' % (self.uid, self.url, self.title, self.description,)

    def get_filename(self, download_dir):
        filename = download_dir + self.filename_prefix + '%(id)s.%(ext)s'
        return filename

    def download(self, download_dir="./"):
        ydl_options = {
            'outtmpl': self.get_filename(download_dir),
            'writethumbnail': True,
            'no_warnings': True,
            'continuedl': False,
            'restrictfilenames': True,
            'quiet': False,
            # Note the format specification is important so we get mp4 and not taller than 480
            'format': "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]"
        }
        with youtube_dl.YoutubeDL(ydl_options) as ydl:
            pp = pprint.PrettyPrinter()
            try:
                ydl.add_default_info_extractors()
                vinfo = ydl.extract_info(self.url, download=True)
                # Save the remaining "temporary scraped values" of attributes with actual values
                # from the video metadata.
                # self.uid = vinfo.get('id', '')
                # self.title = vinfo.get('title', '')
                # pp.pprint(self)

                # # These are useful when debugging.
                # del vinfo['formats']  # to keep from printing 100+ lines
                # del vinfo['requested_formats']  # to keep from printing 100+ lines
                # print('==> Printing video info:')
                # pp.pprint(vinfo)
                print('==> NEW', self)
            except (youtube_dl.utils.DownloadError,
                    youtube_dl.utils.ContentTooShortError,
                    youtube_dl.utils.ExtractorError,) as e:
                print('==> PointBVideo.download(): Error downloading videos')
                pp.pprint(e)
                return False
        return True
