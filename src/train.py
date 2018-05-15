import torch
import torch.optim as optim
from torch.autograd import Variable
import random
from random import shuffle
from sklearn.metrics import roc_auc_score

from src.model import RemotionRNN, save_model, load_model
from src.embeddings import get_embeddings
from src.metrics import choose_threshold_by_f1

def get_batches(data, vocabulary, gram_vector_size, batch_size, max_length, target_function):
    text_batch = []
    gram_batch = []
    y = []
    for review in data:
        indices = []
        gram_vectors = []
        target = []
        for sentence in review:
            text = " ".join([word.text for word in sentence])
            indices += vocabulary.get_indices(text)
            gram_vectors += [word.vector for word in sentence]
            target += [target_function(word) for word in sentence]

        indices = vocabulary.pad_indices(indices, max_length)[:max_length]
        for _ in range(max_length-len(gram_vectors)):
            gram_vectors.append([0 for _ in range(gram_vector_size)])
        gram_vectors = gram_vectors[:max_length]
        target += [0 for _ in range(max_length-len(target))]
        target = target[:max_length]

        text_batch.append(indices)
        gram_batch.append(gram_vectors)
        y.append(target)

        if len(text_batch) == batch_size:
            text_var = Variable(torch.LongTensor(text_batch), requires_grad=False)
            gram_var = Variable(torch.FloatTensor(gram_batch), requires_grad=False)
            y_var = Variable(torch.LongTensor(y), requires_grad=False)
            yield text_var, gram_var, y_var
            text_batch = []
            gram_batch = []
            y = []
    if len(text_batch) != 0:
        text_var = Variable(torch.LongTensor(text_batch), requires_grad=False)
        gram_var = Variable(torch.FloatTensor(gram_batch), requires_grad=False)
        y_var = Variable(torch.LongTensor(y), requires_grad=False)
        yield text_var, gram_var, y_var

def do_epoch(model, criterion, text_batch, gram_batch, y, use_cuda, optimizer=None):
    text_batch = text_batch.cuda() if use_cuda else text_batch
    gram_batch = gram_batch.cuda() if use_cuda else gram_batch
    y = y.cuda() if use_cuda else y

    if optimizer is not None:
        model.train()
        optimizer.zero_grad()
    else:
        model.eval()

    predictions = model.forward(text_batch, gram_batch)
    predictions = predictions.transpose(1, 2).unsqueeze(3)
    y = y.unsqueeze(2)
    loss = criterion(predictions, y)
    predictions = predictions.transpose(1, 2).squeeze(3)
    predictions = torch.nn.functional.softmax(predictions, dim=2)

    if optimizer is not None:
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
        optimizer.step()
    return loss.data.item(), predictions

def train_model(train_data,
                vocabulary,
                gram_vector_size,
                target_function,
                batch_size=8,
                max_length=300,
                epochs=15,
                embeddings_size=500,
                rnn_size=32,
                gram_hidden_size=16,
                n_layers=3,
                bidirectional=True,
                lr=0.001,
                val_size=0.2,
                dropout=0.4,
                use_pretrained_embeddings=True,
                embeddings_filename="w2v.txt",
                seed=42):
    random.seed(seed)

    use_cuda = torch.cuda.is_available()

    model = RemotionRNN(vocabulary.size(),
                        embeddings_size,
                        rnn_size,
                        gram_vector_size,
                        gram_hidden_size,
                        n_layers=n_layers,
                        dropout=dropout,
                        bidirectional=bidirectional)
    if use_pretrained_embeddings:
        embeddings = get_embeddings(vocabulary, embeddings_filename)
        model.embedding.weight = torch.nn.Parameter(embeddings, requires_grad=False)
    model = model.cuda() if use_cuda else model

    optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=lr)
    criterion = torch.nn.CrossEntropyLoss(size_average=False)

    train_size = 1 - val_size
    border = int(len(train_data)*train_size)
    shuffle(train_data)
    train_data, val_data = train_data[:border], train_data[border:]

    prev_val_loss = float("inf")
    for epoch in range(epochs):
        train_loss = 0
        train_count = 0
        train_batches = get_batches(train_data, vocabulary,
            gram_vector_size, batch_size, max_length, target_function)
        for text_batch, gram_batch, y in train_batches:
            loss, _ = do_epoch(model, criterion, text_batch, gram_batch, y, use_cuda, optimizer)
            train_loss += loss
            train_count += 1

        val_loss = 0
        val_count = 0
        all_y = []
        all_preds = [[] for _ in range(model.output_size)]
        val_batches = get_batches(val_data, vocabulary, gram_vector_size,
            batch_size, max_length, target_function)
        for text_batch, gram_batch, y in val_batches:
            model.eval()
            loss, predictions = do_epoch(model, criterion, text_batch, gram_batch, y, use_cuda) 
            val_loss += loss
            val_count += 1

            lengths = []
            for i in range(text_batch.size(0)):
                lengths.append(sum([int(elem != 0) for elem in text_batch[i].data]))
            for i in range(y.size(0)):
                all_y += list(y.data[i])[:lengths[i]]
            for i in range(y.size(0)):
                for j in range(model.output_size):
                    all_preds[j] += list(predictions[:,:,j].data[i])[:lengths[i]]
        roc_aucs = []
        for i in range(model.output_size):
            roc_aucs.append(roc_auc_score([int((elem==i)) for elem in all_y], all_preds[i]))

        print("Train loss: {train_loss}, val loss: {val_loss}, val roc_auc: {roc_auc}".format(
            train_loss = train_loss/train_count,
            val_loss = val_loss/val_count,
            roc_auc = roc_aucs
        ))
        save_model(model, optimizer, "model.pt")
        if prev_val_loss < val_loss:
            break
        prev_val_loss = val_loss
    return model
