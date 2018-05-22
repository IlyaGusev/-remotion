import sys
import os
from src.config import Config, get_targets_additionals
from src.parser import get_data
from src.train import train_model
from src.predict import predict
from src.embeddings import shrink_w2v


def main(config_filename):
    config = Config()
    config.load(config_filename)

    train_data, test_data = get_data(config.data_config, config.competition)
    max_length = max(train_data.get_lengths() + test_data.get_lengths())
    vocabulary = train_data.get_vocabulary().merge(test_data.get_vocabulary())
    if not os.path.exists(config.embeddings_filename) and config.data_config.language == "ru":
        shrink_w2v("/media/yallen/My Passport/Models/Vectors/RDT/russian-big-w2v.txt", vocabulary,
                   100000, config.embeddings_filename)
    char_set = train_data.get_char_set()
    print(vocabulary.size())
    print(char_set)

    targets, additionals, rev_categories, output_sizes = get_targets_additionals(train_data)
    train_model(config_filename, train_data, vocabulary, char_set, targets, additionals, output_sizes, max_length)
    predict(config_filename, test_data, vocabulary, char_set,
            targets, additionals, rev_categories)


if __name__ == "__main__":
    main(sys.argv[1])
