import os
import random
from datetime import datetime

import pretty_midi
import numpy as np
from midi2audio import FluidSynth
import matplotlib.pyplot as plt
import IPython.display as ipd
from sklearn.model_selection import train_test_split
import tensorflow as tf

#midi構成(全体_Aメロ_Aメロ'_Bメロ_サビ_Cメロ_ラスサビ_イントロ)

# 例外オブジェクトを作るためのクラスを定義
# 読み込んだMIDIファイルが本書が定める条件に合わない場合に
# このクラスによって定義される例外が投げられる
class UnsupportedMidiFileException(Exception):
  "Unsupported MIDI File"

def getMIDfiles(directory):
    files = []
    for file in os.listdir(directory):
        base, ext = os.path.splitext(file)
        if base[0] != '.' and ext == '.mid':
            path = os.path.join(directory, file)
            path = os.path.normpath(path)  # パスを正規化
            files.append(path)
    return files

# 与えられたMIDIデータをハ長調またはハ短調に移調
# key_number: 調を表す整数（0--11: 長調、12--23: 短調）
def transpose_to_c(midi, key_number):
  for instr in midi.instruments:               
    if not instr.is_drum:
      for note in instr.notes:
        note.pitch -= key_number % 12

# 与えられたMIDIデータからピアノロール2値行列を取得
# nn_from: 音高の下限値（この値を含む）
# nn_thru: 音高の上限値（この値を含まない）
# seqlen: 読み込む長さ（時間軸方向の要素数、八分音符単位）
# tempo: テンポ
def get_pianoroll(midi, nn_from, nn_thru, seqlen, tempo):
  pianoroll = midi.get_piano_roll(fs=2*round(tempo,6)/60)  # 北原本からの修正
  if pianoroll.shape[1] < seqlen:
    raise UnsupportedMidiFileException
  pianoroll = pianoroll[nn_from:nn_thru, 0:seqlen]
  pianoroll = np.heaviside(pianoroll, 0)
  return np.transpose(pianoroll)

# 指定されたMIDIファイルを読み込んでピアノロール2値行列を返却
# filename: 読み込むファイル名
# sop_alto: ソプラノパートとアルトパートを別々に読み込む場合にTrue
# seqlen: 読み込む長さ（時間軸方向の要素数、八分音符単位）
def read_midi(filename, sop_alto, seqlen):
  # MIDIファイルを読み込む
  midi = pretty_midi.PrettyMIDI(filename)
  # 途中で転調がある場合は対象外として例外を投げる
  if len(midi.key_signature_changes) != 1:
    raise UnsupportedMidiFileException
  # ハ長調またはハ短調に移調する
  key_number = midi.key_signature_changes[0].key_number
  transpose_to_c(midi, key_number)
  # 長調(keymode=0)か短調(keynode=1)かを取得する
  keymode = np.array([int(key_number / 12)])
  # 途中でテンポが変わる場合は対象外として例外を投げる
  tempo_time, tempo = midi.get_tempo_changes()
  if len(tempo) != 1:
    raise UnsupportedMidiFileException
  if sop_alto:
    # パート数が2未満の場合は対象外として例外を投げる
    if len(midi.instruments) < 2:
      raise UnsupportedMidiFileException
    # ソプラノ（1パート目）とアルト（2パート目）のそれぞれに対して
    # ピアノロール2値行列を取得する
    pr_s = get_pianoroll(midi.instruments[0], 36, 84,
                         seqlen, tempo[0])
    pr_a = get_pianoroll(midi.instruments[1], 36, 84,
                         seqlen, tempo[0])
    return pr_s, pr_a, keymode
  else:
    # 全パートを1つにしたピアノロールを取得する
    pr = get_pianoroll(midi, 36, 84, seqlen, tempo[0])
    return pr, keymode
  
# 与えられたピアノロール2値行列からMIDIデータを生成し、ファイルに保存
# pianorolls: ピアノロール2値行列（複数可）を格納した配列
# filename: 保存する際のファイル名
def make_midi(pianorolls, filename):
  midi = pretty_midi.PrettyMIDI(resolution=480)
  for pianoroll in pianorolls:
    instr = pretty_midi.Instrument(program=1)
    for i in range(pianoroll.shape[0]):
      for j in range(pianoroll.shape[1]):
        # ピアノロール2値行列の各要素の値が0.5より大きいときに、
  # その時刻にその音高の音を挿入する
        if pianoroll[i][j] > 0.5:
          instr.notes.append(pretty_midi.Note(start=0.50*i,
                                              end=0.50*(i+1),
                                              pitch=36+j,
                                              velocity=100))
    midi.instruments.append(instr)
  midi.write(filename)

# 与えられたピアノロール2値行列からMIDIデータを作るのに加え、
# ピアノロール2値行列を描画したり、再生できるようにする
def show_and_play_midi(pianorolls, filename, sound_font_path):
  # ピアノロール2値行列を描画する
  for pr in pianorolls:
    plt.matshow(np.transpose(pr), aspect='auto', origin='lower')
    plt.show()
  # MIDIデータを生成してファイルに保存する
  make_midi(pianorolls, filename)
  # MIDIデータをwavに変換してブラウザ上で聴けるようにする
  #fs = FluidSynth(sound_font=sound_font_path)
  #print(fs,filename)
  #fs.midi_to_audio(filename, '自由課題\output.wav')
  #ipd.display(ipd.Audio('自由課題\output.wav'))

def add_rest_nodes(pianoroll):
  # ピアノロール2値行列の時刻ごとの各音高ベクトルに対して、
  # 全要素が0のときに1、そうでないときに0を格納したデータ
  # （休符要素系列と呼ぶ）を作る
  rests = 1 - np.sum(pianoroll, axis=1)
  # 休符要素系列に2次元配列化して行列として扱えるようにする
  rests = np.expand_dims(rests, 1)
  # ピアノロール2値行列と休符要素系列をくっつけた行列を作って返す
  return np.concatenate([pianoroll, rests], axis=1)

directory = "自由課題\chorales\midi"
sound_font_path = "C:/soundfonts/FluidR3_GM.sf2"

x_all = []       # 入力データ（ソプラノメロディ）を格納する配列
y_all = []       # 出力データ（アルトメロディ）を格納する配列
keymodes = []    # 長調か短調かを格納する配列
files = getMIDfiles(directory)       # 読み込んだMIDIファイルのファイル名を格納する配列

# 指定されたフォルダにある全MIDIファイルに対して
# 次の処理を繰り返す
for f in files:
  print(f)
  try:
    # MIDIファイルを読み込む
    # pr_s：ソプラノパートのピアノロール2値行列
    # pr_a：アルトパートのピアノロール2値行列
    # keymode：調（長調：0、短調：1）
    pr_s,  pr_a, keymode = read_midi(f, True, 64)
    # ピアノロール2値行列に休符要素を追加する
    x = add_rest_nodes(pr_s)
    y = add_rest_nodes(pr_a)
    # 休符要素を追加したピアノロール2値行列などを配列に追加する
    x_all.append(x)
    y_all.append(y)
    keymodes.append(keymode)
  # 要件を満たさないMIDIファイルの場合はskipと出力して次に進む
  except UnsupportedMidiFileException:
    i = files.index(f)
    del files[i]
    print("skip")

# あとで扱いやすいように、x_allとy_allをNumPy配列に変換する
x_all = np.array(x_all)
y_all = np.array(y_all)

print(x_all.shape)
print(y_all.shape)

# 学習データとテストデータを1:1の割合で割り当てる
# i_train：学習データの添え字、i_test：テストデータの添え字
i_train, i_test = train_test_split(range(len(x_all)),
                                  test_size=int(len(x_all)/2),
                                  shuffle=False)
x_train = x_all[i_train]
x_test = x_all[i_test]
y_train = y_all[i_train]
y_test = y_all[i_test]


seq_length = x_train.shape[1]      # 時系列の長さ（時間方向の
                                   # 要素数）
input_dim = x_train.shape[2]       # 入力の各要素の次元数
output_dim = y_train.shape[2]      # 出力の各要素の次元数

# 空のモデルを作る
model = tf.keras.Sequential()
# RNN層を作ってモデルに追加する
model.add(tf.keras.layers.SimpleRNN(
    128, input_shape=(seq_length, input_dim), use_bias=True,
    activation="tanh", return_sequences=True))
# 出力層を作ってモデルに追加する
model.add(tf.keras.layers.Dense(
    output_dim, use_bias=True, activation="softmax"))
# 最後の設定を行う
model.compile(optimizer="adam", loss="categorical_crossentropy",
              metrics=["categorical_accuracy"]) # リストに修正
# モデルの構造を画面出力する
model.summary()

# x_train[i]を入力したらy_train[i]が出力されるように
# モデルを学習する（モデルのパラメータの値を決める）
model.fit(x_train, y_train, batch_size=32, epochs=1000)

# テストデータを与えてモデルを評価する
# x_test：テスト用入力データ、y_test：テスト用正解出力データ
model.evaluate(x_test, y_test)

# モデルにテストデータのソプラノを与えてアルトを予測（生成）
y_pred = model.predict(x_test)

# 学習済みモデルの内容を表示
for layer in model.layers:
    print(f"Layer: {layer.name}")
    for i, param in enumerate(layer.get_weights()):
        print(f"Param {i}: {param.shape}\n{param}")


k =random.randint(0, len(x_test))
print("melody id: ", k)

# 選択したデータのアルトの生成結果を聴けるようにする
show_and_play_midi([x_test[k, :, 0:-1], y_pred[k, :, 0:-1]],
                   '自由課題\output.mid',sound_font_path)

# 現在の日時を取得
now = datetime.now()

# 日付と時刻を文字列としてフォーマット
timestamp = now.strftime("%Y%m%d_%H%M%S")

# モデル名に日時を追加
model_name = f"mymodelRNN"

# モデルを保存
model.save(model_name)






