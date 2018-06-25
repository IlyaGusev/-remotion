import xml.etree.ElementTree as ET
from nltk.tokenize import WordPunctTokenizer
from sentence_splitter import SentenceSplitter

from src.parser import Word, Dataset


class Aspect(object):
    def __init__(self, begin=0, end=0, target="", polarity=1, category="", aspect_type=0, mark=0):
        self.type_values = {
            'explicit': 0,
            'implicit': 1,
            'fct': 2
        }
        self.rev_type_values = {value: key for key, value in self.type_values.items()}

        self.sentiment_values = {
            'positive': 3,
            'neutral': 1,
            'negative': 0,
            'both': 2
        }
        self.rev_sentiment_values = {value: key for key, value in self.sentiment_values.items()}

        self.mark_values = {
            'Rel': 0,
            'Irr': 1,
            'Cmpr': 2,
            'Prev': 3,
            'Irn': 4
        }
        self.rev_mark_values = {value: key for key, value in self.mark_values.items()}

        self.begin = begin
        self.end = end
        self.target = target
        self.polarity = polarity
        self.category = category
        self.type = aspect_type
        self.mark = mark
        self.words = []

    def parse(self, node):
        self.begin = int(node.get('from'))
        self.end = int(node.get('to'))
        self.target = node.get('term')
        self.polarity = self.sentiment_values[node.get('sentiment')]
        self.category = node.get('category')
        self.type = self.type_values[node.get('type')]
        self.mark = self.mark_values[node.get('mark')]

    def is_empty(self):
        return self.target == ""

    def inflate_target(self):
        self.target = " ".join([word.text for word in self.words]).replace('"', "'").replace('&', '#')

    def to_xml(self):
        return '<aspect mark="{mark}" category="{category}" type="{aspect_type}" from="{begin}" to="{end}" sentiment="{polarity}" term="{term}"/>\n'.format(
            begin=self.begin, end=self.end, term=self.target, mark=self.rev_mark_values[self.mark],
            aspect_type=self.rev_type_values[self.type], category=self.category,
            polarity=self.rev_sentiment_values[self.polarity])

    def __repr__(self):
        return "<Aspect {begin}:{end} {t} {category} {polarity} at {hid}>".format(
            begin=self.begin,
            end=self.end,
            category=self.category,
            polarity=self.polarity,
            t=self.type,
            hid=hex(id(self))
        )


class Review(object):
    def __init__(self, text="", rid=0):
        self.text = text
        self.rid = rid
        self.aspects = []
        self.sentences = []
        self.categories = {}
        self.sentiment_values = {
            'positive': 3,
            'neutral': 1,
            'negative': 0,
            'both': 2,
            'absence': 4
        }

        self.rev_sentiment_values = {value: key for key, value in self.sentiment_values.items()}

    def parse(self, node):
        self.text = node.find(".//text").text
        self.rid = node.get("id")
        self.aspects = []
        for aspect_node in node.findall(".//aspect"):
            aspect = Aspect()
            aspect.parse(aspect_node)
            self.aspects.append(aspect)
        for category_node in node.findall(".//category"):
            category_name = category_node.get('name')
            sentiment = category_node.get('sentiment')
            self.categories[category_name] = self.sentiment_values[sentiment]

    def to_xml(self):
        aspects_xml = "".join([aspect.to_xml() for aspect in self.aspects])
        categories_xml = ''
        for name, sentiment_num in self.categories.items():
            categories_xml += '<category name="{name}" sentiment="{sentiment}"/>\n'.format(
                name=name,
                sentiment=self.rev_sentiment_values[sentiment_num]
            )

        return '<review id="{rid}">\n<categories>\n{categories}</categories>\n<text>{text}</text>\n<aspects>\n{aspects}</aspects>\n</review>\n'.format(
            rid=self.rid,
            text=self.text.replace("&", "#"),
            aspects=aspects_xml,
            categories=categories_xml)


class SentiRuEvalDataset(Dataset):
    def __init__(self):
        super().__init__()
        self.language = "ru"

    def parse(self, filename, vectorizer=None):
        assert filename.endswith('xml')
        tree = ET.parse(filename)
        root = tree.getroot()
        self.reviews = []
        for review_node in root.findall(".//review"):
            review = Review()
            review.parse(review_node)
            self.reviews.append(review)
        self.tokenize()
        self.pos_tag()

    def tokenize(self):
        sentence_splitter = SentenceSplitter(language='ru')
        for i, review in enumerate(self.reviews):
            text = review.text
            sentences = sentence_splitter.split(text)
            words_borders = list(WordPunctTokenizer().span_tokenize(text))
            for sentence in sentences:
                tokenized_sentence = []
                sentence_begin = text.find(sentence)
                sentence_end = sentence_begin + len(sentence)
                for word_begin, word_end in words_borders:
                    if word_begin >= sentence_begin and word_end <= sentence_end:
                        word_text = text[word_begin: word_end]
                        word = Word(word_text, word_begin, word_end)
                        for opinion in review.aspects:
                            if word.begin >= opinion.begin and word.end <= opinion.end:
                                word.add_opinion(opinion)
                                opinion.words.append(word)
                        tokenized_sentence.append(word)
                self.reviews[i].sentences.append(tokenized_sentence)

    def print_stat(self):
        print("Num of reviews: " + str(len(self.reviews)))
        print("Num of opinions: " + str(self.get_opinion_count()))
        print("Max review length: " + str(max(self.get_lengths())))
        print(self.reviews[0].sentences[0])
        print(self.reviews[0].sentences[0])

    def get_aspect_categories(self):
        categories = set()
        for review in self.reviews:
            for aspect in review.aspects:
                categories.add(aspect.category)
        categories = list(sorted(list(categories)))
        return {category: i for i, category in enumerate(categories)}

    def get_review_categories(self):
        categories = set()
        for review in self.reviews:
            for category in review.categories.keys():
                categories.add(category)
        categories = list(sorted(list(categories)))
        return {category: i for i, category in enumerate(categories)}
