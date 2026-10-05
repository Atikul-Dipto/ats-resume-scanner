"""Two-tower matching encoder with a SHARED (Siamese) tower.

Resumes and job postings are the same kind of content (free text describing
skills, titles, and experience), so one encoder embeds both into a shared
vector space rather than training two separately-weighted towers for
genuinely different modalities. This is what makes the matching "two-way":
candidate -> job and job -> candidate ranking both reduce to the same
cosine-similarity lookup in one embedding space.

Trained with in-batch-negative contrastive loss: for a batch of N
(anchor, positive) pairs, the N x N similarity matrix has true pairs on the
diagonal and every other pairing in the batch acts as an implicit negative.
"""

import tensorflow as tf
from tensorflow import keras

VOCAB_SIZE = 8000
SEQUENCE_LENGTH = 64
EMBEDDING_DIM = 64
HIDDEN_DIM = 128


def build_vectorizer(texts: list[str]) -> keras.layers.TextVectorization:
    vectorizer = keras.layers.TextVectorization(
        max_tokens=VOCAB_SIZE,
        output_sequence_length=SEQUENCE_LENGTH,
        standardize="lower_and_strip_punctuation",
    )
    vectorizer.adapt(texts)
    return vectorizer


def build_encoder(vectorizer: keras.layers.TextVectorization) -> keras.Model:
    """Text -> L2-normalized embedding. This is the shared tower."""
    text_input = keras.Input(shape=(1,), dtype=tf.string, name="text")
    token_ids = vectorizer(text_input)
    embedded = keras.layers.Embedding(
        input_dim=VOCAB_SIZE, output_dim=EMBEDDING_DIM, mask_zero=True, name="token_embedding"
    )(token_ids)
    pooled = keras.layers.GlobalAveragePooling1D()(embedded)
    hidden = keras.layers.Dense(HIDDEN_DIM, activation="relu", name="hidden")(pooled)
    projected = keras.layers.Dense(EMBEDDING_DIM, name="projection")(hidden)
    normalized = keras.layers.Lambda(
        lambda x: tf.math.l2_normalize(x, axis=1), name="l2_normalize"
    )(projected)
    return keras.Model(text_input, normalized, name="shared_encoder")


class InBatchContrastiveModel(keras.Model):
    """Wraps the shared encoder to train on (anchor, positive) pairs."""

    def __init__(self, encoder: keras.Model, temperature: float = 0.05, **kwargs):
        super().__init__(**kwargs)
        self.encoder = encoder
        self.temperature = temperature

    def call(self, inputs):
        anchor_text, positive_text = inputs
        return self.encoder(anchor_text), self.encoder(positive_text)

    def train_step(self, data):
        anchor_text, positive_text = data
        batch_size = tf.shape(anchor_text)[0]

        with tf.GradientTape() as tape:
            anchor_emb = self.encoder(anchor_text, training=True)
            positive_emb = self.encoder(positive_text, training=True)
            similarity = tf.matmul(anchor_emb, positive_emb, transpose_b=True) / self.temperature
            labels = tf.range(batch_size)
            loss = keras.losses.sparse_categorical_crossentropy(
                labels, similarity, from_logits=True
            )
            loss = tf.reduce_mean(loss)

        gradients = tape.gradient(loss, self.encoder.trainable_variables)
        self.optimizer.apply_gradients(zip(gradients, self.encoder.trainable_variables, strict=False))

        predicted = tf.argmax(similarity, axis=1, output_type=tf.int32)
        accuracy = tf.reduce_mean(tf.cast(tf.equal(predicted, labels), tf.float32))
        return {"loss": loss, "in_batch_accuracy": accuracy}
