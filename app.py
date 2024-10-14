from flask import Flask, jsonify, request, url_for, send_from_directory
import os
from werkzeug.utils import secure_filename
from loguru import logger
import easyocr
import cv2

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
UPLOAD_FOLDER = './uploads'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Função para verificar se a extensão do arquivo é permitida
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Função para desenhar as caixas delimitadoras na imagem
def draw_boxes(image_path, results):
    image = cv2.imread(image_path)
    for result in results:
        top_left = tuple(result[0][0])
        bottom_right = tuple(result[0][2])
        cv2.rectangle(image, top_left, bottom_right, (0, 255, 0), 2)  
        text = result[1]
        cv2.putText(image, text, top_left, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2, cv2.LINE_AA)  # Escreve o texto
    output_path = image_path.replace("uploads", "outputs")
    cv2.imwrite(output_path, image)
    return output_path

# Função para realizar OCR e filtragem de texto da placa
class PlateDataAnalysis:
    def __init__(self):
        self.reader = easyocr.Reader(['pt', 'en'])

    def read_text_from_image(self, image_path, decoder):
        results = self.reader.readtext(image_path, decoder=decoder)
        return results

    def filter_plates(self, results):
        potential_plates = []
        for result in results:
            text, confidence = result[1], result[2]
            logger.info(f'extracted text: {text} precision {confidence}')
            if confidence > 0.3 and len(text) >= 7:
                potential_plates.append({
                    'text': text,
                    'confidence': confidence
                })
        return potential_plates if potential_plates else None


@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image part in the request'}), 400

    file = request.files['image']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        logger.info(f'Image saved at {file_path}')

        # Processar a imagem e realizar OCR
        plate_analysis = PlateDataAnalysis()
        texts = plate_analysis.read_text_from_image(file_path, 'beamsearch')
        text_plate = plate_analysis.filter_plates(texts)

        # Desenhar caixas nas letras detectadas
        output_image_path = draw_boxes(file_path, texts)

        response = {
            'image_url': url_for('uploaded_file', filename=output_image_path.split('/')[-1], _external=True),
            'detected_texts': [{'text': item[1], 'confidence': item[2]} for item in texts],
            'plates': text_plate if text_plate else 'No potential plates found'
        }

        return jsonify(response), 200

    return jsonify({'error': 'File type not allowed'}), 400

# Rota para servir arquivos de imagem carregados
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Rota para servir as imagens processadas com as caixas
@app.route('/outputs/<filename>')
def output_file(filename):
    return send_from_directory('./outputs', filename)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if not os.path.exists('./outputs'):
        os.makedirs('./outputs')
    app.run(debug=True)
