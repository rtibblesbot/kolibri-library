from bs4 import BeautifulSoup
from bs4.element import Tag
from urllib.parse import urlsplit
filenames = """
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/youre-invited-to-a-ceili-exploring-irish-dance.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_dance.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_dance.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish-dancers.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish-shoes.ashx
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_costumes_2.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_costumes_3.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/irish_costumes_4.jpg
   https://artsedge.kennedy-center.org/~/media/ArtsEdge/Images/LessonArt/grade-3-4/ceili/stolen-child.ashx
""".strip().split("\n")

filenames = [x.strip() for x in filenames]

with open("html/play_template.html", "rb") as f:
    html_bytes = f.read()

soup = BeautifulSoup(html_bytes, "html5lib")

small_slick_replace, large_slick_replace = soup.findAll("divreplace")

large_slick = soup.new_tag("placeholder")
for filename in filenames:
    div_tag = soup.new_tag("div")
    img_tag = soup.new_tag("img")
    img_tag.attrs['src'] = filename # TODO fix /~/
    div_tag.insert(0, img_tag)
    large_slick.insert(0, div_tag)


small_slick = soup.new_tag("placeholder")
for filename in filenames:
    div_tag = soup.new_tag("div")
    img_tag = soup.new_tag("img")
    img_tag.attrs['src'] = filename # TODO fix /~/
    img_tag.attrs['width'] = 100
    img_tag.attrs['height'] = 100
    div_tag.insert(0, img_tag)
    small_slick.insert(0, div_tag)

large_slick_replace.replace_with(large_slick)
small_slick_replace.replace_with(small_slick) # TODO make small_slick different.
large_slick.replaceWithChildren()
small_slick.replaceWithChildren()

print (soup)

with open("html/play_output.html", "w") as f:
    f.write(soup.prettify())
