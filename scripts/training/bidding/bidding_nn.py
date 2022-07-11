import sys
sys.path.append('../../../src')

import os.path
import numpy as np
import tensorflow as tf
tf.compat.v1.disable_eager_execution()

from batcher import Batcher

bin_dir = sys.argv[1]
out_dir = sys.argv[2]

model_path = os.path.join(out_dir, 'bidding')

batch_size = 100
n_iterations = 1000000
display_step = 10000
n_iterations = 10000

X_train = np.load(os.path.join(bin_dir, 'X.npy'))
y_train = np.load(os.path.join(bin_dir, 'y.npy'))

# (2352, 8, 159) (2352, 8, 40)
print(X_train.shape, y_train.shape)

n_examples = y_train.shape[0]
n_ftrs = X_train.shape[2]
n_bids = y_train.shape[2]

lstm_size = 128
n_layers = 3

keep_prob = tf.compat.v1.placeholder(tf.float32, name='keep_prob')

cells = []
for _ in range(n_layers):
    cell = tf.compat.v1.nn.rnn_cell.DropoutWrapper(
        tf.compat.v1.nn.rnn_cell.BasicLSTMCell(lstm_size),
        output_keep_prob=keep_prob
    )
    cells.append(cell)

state = []
for i, cell_i in enumerate(cells):
    s_c = tf.compat.v1.placeholder(tf.float32, [1, lstm_size], name='state_c_{}'.format(i))
    s_h = tf.compat.v1.placeholder(tf.float32, [1, lstm_size], name='state_h_{}'.format(i))
    state.append(tf.compat.v1.nn.rnn_cell.LSTMStateTuple(c=s_c, h=s_h))
state = tuple(state)

x_in = tf.compat.v1.placeholder(tf.float32, [1, n_ftrs], name='x_in')
    
lstm_cell = tf.compat.v1.nn.rnn_cell.MultiRNNCell(cells)

seq_in = tf.compat.v1.placeholder(tf.float32, [None, None, n_ftrs], 'seq_in')
seq_out = tf.compat.v1.placeholder(tf.float32, [None, None, n_bids], 'seq_out')

softmax_w = tf.compat.v1.get_variable('softmax_w', shape=[lstm_cell.output_size, n_bids], dtype=tf.float32, initializer=tf.compat.v1.keras.initializers.VarianceScaling(scale=1.0, mode="fan_avg", distribution="uniform", seed=1337))

out_rnn, _ = tf.compat.v1.nn.dynamic_rnn(lstm_cell, seq_in, dtype=tf.float32)

out_bid_logit = tf.matmul(tf.reshape(out_rnn, [-1, lstm_size]), softmax_w, name='out_bid_logit')
out_bid_target = tf.reshape(seq_out, [-1, n_bids], name='out_bid_target')

output, next_state = lstm_cell(x_in, state)

# TODO figure out why they are not on the same graph
#out_bid_logit2 = tf.matmul(output, softmax_w, name='out_bid_logit2')
#out_bid = tf.nn.softmax(out_bid_logit2, name='out_bid')

for i, next_i in enumerate(next_state):
    tf.identity(next_i.c, name='next_c_{}'.format(i))
    tf.identity(next_i.h, name='next_h_{}'.format(i))

cost = tf.compat.v1.losses.softmax_cross_entropy(out_bid_target, out_bid_logit)

train_step = tf.compat.v1.train.AdamOptimizer(0.001).minimize(cost)

batch = Batcher(n_examples, batch_size)
cost_batch = Batcher(n_examples, display_step)

with tf.compat.v1.Session() as sess:
    sess.run(tf.compat.v1.global_variables_initializer())

    saver = tf.compat.v1.train.Saver(max_to_keep=100)

    for i in range(n_iterations):
        x_batch, y_batch = batch.next_batch([X_train, y_train])
        if i % display_step == 0:
            x_cost, y_cost = cost_batch.next_batch([X_train, y_train])
            c_train = sess.run(cost, feed_dict={seq_in: x_cost, seq_out: y_cost, keep_prob: 1.0})
            print('{}. c_train={}'.format(i, c_train))
            sys.stdout.flush()
            saver.save(sess, model_path, global_step=i)
        sess.run(train_step, feed_dict={seq_in: x_batch, seq_out: y_batch, keep_prob: 0.8})

    saver.save(sess, model_path, global_step=n_iterations)
