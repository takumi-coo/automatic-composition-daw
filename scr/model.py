import pretty_midi
import os
from collections import Counter
import numpy as np
import tensorflow as tf

from sklearn.model_selection import train_test_split

key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
N=100

KEY_LENGTH=89
NOTE_LENGTH=64

class UnsupportedMidiFileException(Exception):
    "Unsupported MIDI File"

def getMIDIfiles(directory):
    files = []
    for file in os.listdir(directory):
        base, ext = os.path.splitext(file)
        if base[0] != '.' and ext == '.mid':
            path = os.path.join(directory, file)
            path = os.path.normpath(path)  # パスを正規化
            files.append(path)
    return files

# 与えられたMIDIデータをCメジャーまたはAマイナーに移調
def transpose_to_c_or_a_minor(midi, key_number, is_major):
    semitones = -key_number % 12 if is_major else (9 - key_number) % 12
    if semitones >= 6:
        semitones -= 12
    for instr in midi.instruments:
        if not instr.is_drum:
            for note in instr.notes:
                note.pitch += semitones

def estimate_key(midi_file_path):
    # MIDIファイルを読み込む
    midi_data = pretty_midi.PrettyMIDI(midi_file_path)


    # 途中で転調がある場合は対象外として例外を投げる
    if len(midi_data.key_signature_changes) != 1:
      raise UnsupportedMidiFileException
    
    # 途中でテンポが変わる場合は対象外として例外を投げる
    tempo_time, tempo = midi_data.get_tempo_changes()
    if len(tempo) != 1:
        raise UnsupportedMidiFileException
    
    # 全てのノートを収集する
    notes = []
    for instrument in midi_data.instruments:
        if not instrument.is_drum:  # ドラムを除外する
            notes.extend([note.pitch % 12 for note in instrument.notes])
    
    # 各ノートの頻度をカウントする
    note_counts = Counter(notes)
    
    # 音名とキーのマッピング
    major_scale_offsets = [0, 2, 4, 5, 7, 9, 11]
    minor_scale_offsets = [0, 2, 3, 5, 7, 8, 10]
    
    # 各キーのスコアを計算する
    key_scores = {}
    for key in range(12):
        major_score = sum(note_counts[(key + offset) % 12] for offset in major_scale_offsets)
        minor_score = sum(note_counts[(key + offset) % 12] for offset in minor_scale_offsets)
        key_scores[key] = {'major': major_score, 'minor': minor_score}
    
    # 最もスコアの高いキーを見つける
    best_key = max(key_scores, key=lambda k: max(key_scores[k]['major'], key_scores[k]['minor']))
    is_major = key_scores[best_key]['major'] >= key_scores[best_key]['minor']

    if is_major:
        estimated_key = key_names[best_key] + ' Major'
    else:
        parallel_major_key = key_names[(best_key + 3) % 12] + ' Major'
        estimated_key = parallel_major_key

    transpose_to_c_or_a_minor(midi_data, best_key, is_major)
    
    return midi_data, best_key, is_major, estimated_key

def extract_notes_with_rests(midi_data):
    notes_info = []
    
    # テンポを取得（全てのテンポが同じであると仮定）
    tempo = midi_data.get_tempo_changes()[1][0]
    
    # 1拍の長さを秒単位で計算
    beat_length_in_seconds = 60.0 / tempo
    
    # 各インストゥルメントをループしてノート情報を取得する
    instrument = midi_data.instruments[0]  # 仮に最初のインストゥルメントを使用
    # ノートを開始時間でソート
    instrument.notes.sort(key=lambda note: note.start)
    
    # ノートの開始位置を初期化
    previous_note_end = 0

    # 最初のノート前の休符をチェック
    if instrument.notes[0].start > 0:
        rest_length_in_seconds = instrument.notes[0].start
        rest_length_in_beats = rest_length_in_seconds / beat_length_in_seconds
        num_sixteenth_notes = int(rest_length_in_beats / 0.25)
        if num_sixteenth_notes < 16:
            for j in range(num_sixteenth_notes):
                if j == 0 and num_sixteenth_notes == 1:
                    notes_info.append([-1, 0])
                else:
                    notes_info.append([-1, num_sixteenth_notes-1])

    # 各ノートと次のノートの間にある休符の検出
    for i in range(len(instrument.notes)):
        note = instrument.notes[i]
        note_number = note.pitch
        note_length_in_seconds = note.end - note.start
        note_length_in_beats = note_length_in_seconds / beat_length_in_seconds
        num_sixteenth_notes = int(note_length_in_beats / 0.25)
        
        for j in range(num_sixteenth_notes):
            if j == 0 and num_sixteenth_notes == 1:
                notes_info.append([note_number, 0])
            else:
                notes_info.append([note_number, num_sixteenth_notes-1])
        
        previous_note_end = note.end
        
        # 次のノートまでの休符を計算
        if i < len(instrument.notes) - 1:
            next_note_start = instrument.notes[i + 1].start
            rest_length_in_seconds = next_note_start - previous_note_end
            if rest_length_in_seconds > 0:
                rest_length_in_beats = rest_length_in_seconds / beat_length_in_seconds
                num_sixteenth_notes = int(rest_length_in_beats / 0.25)
                for j in range(num_sixteenth_notes):
                    if j == 0 and num_sixteenth_notes == 1:
                        notes_info.append([-1, 0])
                    else:
                        notes_info.append([-1, num_sixteenth_notes-1])

    

    return notes_info


def create_sequences(notes_info, seq_length):
    sequences = []
    next_notes = []
    for i in range(len(notes_info) - seq_length):
        pianoroll = [0 for i in range(KEY_LENGTH)]#88鍵+休符
        note_length = [0 for i in range(NOTE_LENGTH)]#4小節分
        seq_in = notes_info[i:i + seq_length]
        next_note = notes_info[i + seq_length]

        if next_note[0]>=KEY_LENGTH or next_note[1]>=NOTE_LENGTH:
            continue
        else:
            if next_note[0]>0:
                pianoroll[next_note[0]]=1
            else: 
                pianoroll[-1]=1
            note_length[next_note[1]]=1
            seq_out = pianoroll + note_length

            sequences.append(seq_in)
            next_notes.append(seq_out)
        

    return np.array(sequences), np.array(next_notes)


def build_model(input_shape):
    model = tf.keras.Sequential()
    model.add(tf.keras.layers.LSTM(128, input_shape=input_shape, return_sequences=True))
    model.add(tf.keras.layers.Dropout(0.2))
    model.add(tf.keras.layers.LSTM(128))
    model.add(tf.keras.layers.Dropout(0.2))
    model.add(tf.keras.layers.Dense(KEY_LENGTH+NOTE_LENGTH, activation='linear'))
    model.compile(loss='mean_squared_error', optimizer='adam')
    return model

def build_model_RNN(input_shape):
    model = tf.keras.Sequential()
    model.add(tf.keras.layers.SimpleRNN(128, input_shape=input_shape, return_sequences=True))
    model.add(tf.keras.layers.Dropout(0.2))
    model.add(tf.keras.layers.SimpleRNN(128))
    model.add(tf.keras.layers.Dropout(0.2))
    model.add(tf.keras.layers.Dense(KEY_LENGTH+NOTE_LENGTH, activation='linear'))
    model.compile(loss='mean_squared_error', optimizer='adam')
    return model


directory = 'data'
files = getMIDIfiles(directory)

seq_length=64#(4小節)

all_sequences = []
all_next_notes = []

np.set_printoptions(precision=5)
for i,file in enumerate(files):
    
    try:
      midi, best_key, is_major, estimated_key = estimate_key(file)
      noteline = extract_notes_with_rests(midi)
      if len(noteline)>seq_length:
        sequences, next_notes = create_sequences(noteline,seq_length)
        all_sequences.append(sequences)
        all_next_notes.append(next_notes)
    except UnsupportedMidiFileException:
      i = files.index(file)
      del files[i]
      print("skip")

for i,seq in enumerate(all_sequences):
    print(i,seq.shape)

# シーケンスと次のノートを結合
all_sequences = np.vstack(all_sequences)
all_next_notes = np.vstack(all_next_notes)


# データの形状を変更
X = np.reshape(all_sequences, (all_sequences.shape[0], all_sequences.shape[1], 2))
y = np.reshape(all_next_notes, (all_next_notes.shape[0], all_next_notes.shape[1],1))

# データを学習用とテスト用に分割
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=1)

# モデルを構築
model = build_model_RNN((X.shape[1], X.shape[2]))

# モデルを学習
model.fit(X_train, y_train, epochs=200, batch_size=64, validation_split=0.2)

# テストデータを用いてモデルを評価
test_loss = model.evaluate(X_test, y_test)
print(f'Test Loss: {test_loss}')
model_name = "note_prediction_model_RNN_"+str(seq_length)
ext = ".h5"
path = model_name+ext


# モデルの保存
model.save(path)
