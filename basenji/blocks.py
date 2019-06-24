"""SeqNN blocks"""

import numpy as np
import tensorflow as tf

from basenji import layers

def conv_block(inputs, filters=128, activation='relu', kernel_size=1, strides=1, dilation_rate=1, l2_scale=0, dropout=0, pool_size=1, batch_norm=False, bn_momentum=0.99, bn_gamma='ones'):
  """Construct a single convolution block.

  Args:
    inputs:        [batchsize, length, num_channels] input sequence
    filters:       Conv1D filters
    kernel_size:   Conv1D kernel_size
    activation:    relu/gelu/etc
    strides:       Conv1D strides

  Returns:
    output sequence
  """

  # flow through variable current
  current = inputs

  # activation
  current = layers.activate(current, activation)

  # convolution
  current = tf.keras.layers.Conv1D(
    filters=filters,
    kernel_size=kernel_size,
    strides=strides,
    padding='same',
    use_bias=False,
    dilation_rate=dilation_rate,
    kernel_initializer='he_normal',
    kernel_regularizer=tf.keras.regularizers.l2(l2_scale))(current)

  # batch norm
  if batch_norm:
    current = tf.keras.layers.BatchNormalization(
      momentum=bn_momentum,
      gamma_initializer=bn_gamma,
      fused=True)(current)

  # dropout
  if dropout > 0:
    current = tf.keras.layers.Dropout(rate=dropout)(current)

  # Pool
  if pool_size > 1:
    current = tf.keras.layers.MaxPool1D(
      pool_size=pool_size,
      padding='same')(current)

  return current

def conv_tower(inputs, filters_init, filters_mult=1, repeat=1, **kwargs):
  """Construct a reducing convolution block.

  Args:

  Returns:
    output sequence
  """

  # flow through variable current
  current = inputs

  # initialize filters
  rep_filters = filters_init

  for ri in range(repeat):
    # convolution
    current = conv_block(current,
      filters=int(np.round(rep_filters)),
      **kwargs)

    # update filters
    rep_filters *= filters_mult

  return current


def dense(inputs, units, activation='softplus', l2_scale=0, l1_scale=0, **kwargs):
  current = tf.keras.layers.Dense(
    units=units,
    activation=activation,
    use_bias=True,
    kernel_initializer='he_normal',
    kernel_regularizer=tf.keras.regularizers.l1_l2(l1_scale, l2_scale)
    )(inputs)
  return current


def dilated_dense(inputs, filters, kernel_size=3, rate_mult=2, dropout=0, repeat=1, **kwargs):
  """Construct a residual dilated dense block.

  Args:

  Returns:
  """

  # flow through variable current
  current = inputs

  # initialize dilation rate
  dilation_rate = 1.0

  for ri in range(repeat):
    rep_input = current

    # dilate
    current = conv_block(current,
      filters=filters,
      kernel_size=kernel_size,
      dilation_rate=int(np.round(dilation_rate)),
      **kwargs)

    # dense concat
    current = tf.keras.layers.Concatenate()([rep_input,current])

    # update dilation rate
    dilation_rate *= rate_mult

  return current


def dilated_residual(inputs, filters, kernel_size=3, rate_mult=2, dropout=0, repeat=1, **kwargs):
  """Construct a residual dilated convolution block.

  Args:

  Returns:
  """

  # flow through variable current
  current = inputs

  # initialize dilation rate
  dilation_rate = 1.0

  for ri in range(repeat):
    rep_input = current

    # dilate
    current = conv_block(current,
      filters=filters,
      kernel_size=kernel_size,
      dilation_rate=int(np.round(dilation_rate)),
      bn_gamma='ones',
      **kwargs)

    # return
    current = conv_block(current,
      filters=rep_input.shape[-1],
      dropout=dropout,
      bn_gamma='zeros',
      **kwargs)

    # residual add
    current = tf.keras.layers.Add()([rep_input,current])

    # update dilation rate
    dilation_rate *= rate_mult

  return current


name_func = {
  'conv_block': conv_block,
  'conv_tower': conv_tower,
  'dense': dense,
  'dilated_residual': dilated_residual,
  'dilated_dense': dilated_dense
}

keras_func = {
  'Conv1D': tf.keras.layers.Conv1D,
  'Dense': tf.keras.layers.Dense
}
