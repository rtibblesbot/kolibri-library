# coding=utf-8
page = """

<section class="slide level1">
<p><img src="{image}"></p>
<p>{text}</p>
<audio> <source src="{audio}" </audio>
<center>
<strong>{page}</strong>
</center>
</section>

"""

trailer = """
<section class="slide level1">
<h2 id="en-veldig-høy-mann-1">{title}</h2>
<strong>Tekst:</strong> {author}<br> <strong>Illustrasjoner:</strong> {artist}<br> <strong>Oversettelse:</strong> {narrator}<br> <strong>Språk:</strong> {language}<br> <strong>Lest av:</strong> Espen Stranger-Johannessen<br>
<p>
Denne fortellingen kommer fra <a href='https://global-asp.github.io/'>Global African Storybook Project</a>, som jobber med å oversette fortellingene fra <a href='http://africanstorybook.org/'>African Storybook Project</a> til alle verdens språk.
<p>
Du kan se den originale fortellingen på ASP-websida <a href='http://my.africanstorybook.org/stories/very-tall-man'>her</a>
<p><div class="license">
<a href="https://global-asp.github.io"><img src="https://global-asp.github.io/logo.png" alt="Global ASP logo" border="0" /></a>
</div>
<p><center><div class="license">
<a rel="license" href="http://creativecommons.org/licenses/by/3.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by/3.0/88x31.png" /></a><br />This work is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by/3.0/">Creative Commons Attribution 3.0 Unported License</a>.
</div></center>
</section>
"""

class Carousel(object):
    def __init__(self, data):
        self.data = data
        self.pages = self.pagehtml()
        self.title = data.title
        self.cover = data.cover
        self.coveraudio = data.coveraudio
        self.trailer = self.trailerhtml()

    def html(self):
        with open("template.html") as f:
            html = f.read()
        for item in ["title", "pages", "cover", "trailer", "coveraudio"]:
            assert "**"+item+"**" in html, item
            html = html.replace("**{}**".format(item), getattr(self, item))
        return html

    def pagehtml(self):
        html =  []
        for i, (text, img, audio) in enumerate(zip(self.data.texts, self.data.imgs, self.data.audios)):
            fields = {"text": text,
                      "image": img,
                      "audio": audio,
                      "page": i}
            html.append(page.format(**fields))
        return '\n\n'.join(html)

    def trailerhtml(self):
        return trailer.format(title = self.data.title,
                              author = self.data.author,
                              artist = self.data.artist,
                              narrator = self.data.narrator,
                              language = self.data.language)



