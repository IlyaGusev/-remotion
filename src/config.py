import json
import copy

class ModelConfig(object):
    def __init__(self):
        self.is_sequence_predictor = True
        self.use_crf = False
        self.use_pos = True
        self.use_chars = False
        self.use_word_embeddings = True
        self.use_additional_features = True
        self.is_multi_target = False
        self.target_count = 5
        self.additional_features_size = 1
        self.word_vocabulary_size = 2
        self.word_embedding_dim = 500
        self.word_embedding_dropout_p = 0.2
        self.rnn_n_layers = 2
        self.rnn_hidden_size = 50
        self.rnn_dropout_p = 0.5
        self.rnn_bidirectional = True
        self.rnn_output_dropout_p = 0.3
        self.gram_vector_size = 52
        self.gram_hidden_size = 30
        self.gram_dropout_p = 0.2
        self.char_count = 50
        self.char_embedding_dim = 4
        self.char_function_output_size = 50
        self.char_dropout_p = 0.2
        self.char_max_word_length = 30
        self.dense_size = 32
        self.dense_dropout_p = 0.3
        self.output_size = 3

class DataConfig(object):
    def __init__(self):
        self.language = "en"
        self.competition = "semeval"
        self.domain = "rest"
        self.train_filename = ""
        self.test_filename = ""
        self.vectorizer_path = "vectorizer.json"

class Config(object):
    def __init__(self):
        self.task_type = "a"
        self.embeddings_filename = ""
        self.val_size = 0.2
        self.epochs = 100
        self.lr = 0.001
        self.batch_size = 8
        self.patience = 2
        self.max_length = 300
        self.word_max_length = 30
        self.use_pretrained_embedding = True
        self.data_config = DataConfig()
        self.model_config = ModelConfig()
        self.output_filename = "submission.xml"
        self.seed = 42
        self.model_filename = "model.pt"

    def save(self, filename):
        with open(filename, 'w', encoding='utf-8') as f:
            d = copy.deepcopy(self.__dict__)
            d['model_config'] = self.model_config.__dict__
            d['data_config'] = self.data_config.__dict__
            f.write(json.dumps(d, sort_keys=True, indent=4)+"\n")

    def load(self, filename):
        with open(filename, 'r', encoding='utf-8') as f:
            d = json.loads(f.read())
            self.__dict__.update(d)
            self.model_config = ModelConfig()
            self.model_config.__dict__.update(d['model_config'])
            self.data_config = DataConfig()
            self.data_config.__dict__.update(d['data_config'])

def get_targets_additionals(train_data):
    categories = train_data.get_aspect_categories()
    rev_categories = {value: key for key, value in categories.items()}
    print(categories)
    print(rev_categories)

    def get_target_func_from_word_func(word_func):
        def target_func(review):
            return [word_func(word) for sentence in review.sentences for word in sentence]
        return target_func

    def semeval_word_function_12(word):
        for opinion in word.opinions:
            opinion_category = categories[opinion.cat_first+"#"+opinion.cat_second]
            if opinion.words[0].text == word.text:
                return 2 * opinion_category + 1
            return 2 * opinion_category + 2
        return 0

    def semeval_word_function_3(word):
        for opinion in word.opinions:
            return opinion.polarity + 1
        return 0

    def semeval_additional_function_3(word):
        if word.opinions:
            return [len(word.opinions)]
        return [0]

    targets = {
        'semeval-12': get_target_func_from_word_func(semeval_word_function_12),
        'semeval-3': get_target_func_from_word_func(semeval_word_function_3)
    }

    additionals = {
        'semeval-12': semeval_additional_function_3,
        'semeval-3': None
    }

    return targets, additionals
