from flask import Flask, jsonify, request, url_for, send_from_directory
import os
from werkzeug.utils import secure_filename
from loguru import logger
import cv2
import requests
import easyocr
import re
import numpy as np
import imutils
import matplotlib.pyplot as plt

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

    if image is None:
        logger.error(f'Erro ao carregar a imagem: {image_path}')
        return None

    for result in results:
        try:
            # Verifica se o resultado possui ao menos 4 coordenadas
            if len(result[0]) >= 4:
                top_left = tuple(map(int, result[0][0]))
                bottom_right = tuple(map(int, result[0][2]))
                cv2.rectangle(image, top_left, bottom_right, (0, 255, 0), 2)
                text = result[1]
                cv2.putText(image, text, top_left, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2, cv2.LINE_AA)
        except (IndexError, ValueError) as e:
            logger.error(f'Erro ao processar coordenadas: {e}')

    # Cria a pasta de saída, se não existir
    output_folder = './outputs'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Define o caminho de saída para a imagem
    output_path = os.path.join(output_folder, os.path.basename(image_path))
    cv2.imwrite(output_path, image)
    return output_path

# Função para realizar OCR e filtragem de texto da placa
class PlateDataAnalysis:
    def __init__(self):
        self.reader = easyocr.Reader(['pt', 'en'])

    def process_image(self, image_path):
        # Carregar a imagem
        img = cv2.imread(image_path)

        # Convertendo para escala de cinza
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Aplicando filtro bilateral
        bfilter = cv2.bilateralFilter(gray, 11, 11, 17)

        # Detecção de bordas com Canny
        edged = cv2.Canny(bfilter, 30, 200)

        # Encontrar contornos
        keypoints = cv2.findContours(edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = imutils.grab_contours(keypoints)

        # Ordenar os contornos e pegar os 10 maiores
        contours = sorted(contours, key = cv2.contourArea, reverse = True)[:10]

        location = None
        for contour in contours:
            approx = cv2.approxPolyDP(contour, 10, True)
            if len(approx) == 4:
                location = approx
                break

        # Criar a máscara
        mask = np.zeros(gray.shape, np.uint8)
        cv2.drawContours(mask, [location], 0, 255, -1)

        # Isolar a placa usando a máscara
        new_image = cv2.bitwise_and(img, img, mask=mask)

        # Coordenadas do retângulo
        (x, y) = np.where(mask == 255)
        (x1, y1) = (np.min(x), np.min(y))
        (x2, y2) = (np.max(x), np.max(y))

        # Adicionando um buffer
        cropped_image = gray[x1:x2+3, y1:y2+3]

        return cropped_image

    def read_text_from_image(self, image_path):
        # Realiza o pré-processamento da imagem (recorte da placa)
        cropped_image = self.process_image(image_path)

        # Realizando OCR
        results = []
        decoders = ['beamsearch', 'wordbeamsearch', 'greedy']

        for decoder in decoders:
            logger.info(f"Realizando OCR com o decodificador {decoder}...")
            result = self.reader.readtext(cropped_image, decoder=decoder)
            results.extend(result)  # Adiciona os resultados da execução ao total

        logger.info(f'OCR results (combined from 3 analyses): {results}')
        return results

    def filter_plates(self, results):
        potential_plates = []
        # Definindo o padrão de uma placa Mercosul (ex: ABC1D23)
        plate_pattern = r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$'

        for result in results:
            text, confidence = result[1], result[2]
            logger.info(f'Extracted text: {text} | Confidence: {confidence}')
            
            # Verifica se o texto corresponde ao padrão e tem confiança acima de 0.3
            if confidence > 0.3 and len(text) == 7 and re.match(plate_pattern, text):
                potential_plates.append({
                    'text': text,
                    'confidence': confidence
                })
        return potential_plates if potential_plates else None

# Função para verificar a placa no Adonis js
def check_plate_in_database(plate):
    try:
        response = requests.get(f'http://localhost:3555/search-plate?plate={plate}')
        data = response.json()
        logger.info(f'Entrou na verificação de placas')
        return data.get('message') == 'Placa cadastrada'
    except requests.RequestException as e:
        logger.error(f'Erro ao verificar placa: {e}')
        return False

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

        # Processar a imagem e realiza OCR
        plate_analysis = PlateDataAnalysis()
        texts = plate_analysis.read_text_from_image(file_path)  # Executa o OCR 3 vezes
        text_plate = plate_analysis.filter_plates(texts)

        # Verificar se as placas estão cadastradas na API
        plate_verifications = []
        if text_plate:
            for plate in text_plate:
                verification_result = check_plate_in_database(plate['text'])
                plate_verifications.append({
                    'plate': plate['text'],
                    'confidence': plate['confidence'],
                    'verification': verification_result
                })

        # Desenhar caixas nas letras detectadas
        output_image_path = draw_boxes(file_path, texts)

        if output_image_path is None:
            return jsonify({'error': 'Failed to process image'}), 500

        response = {
            'image_url': url_for('output_file', filename=output_image_path.split('/')[-1], _external=True),
            'detected_texts': [{'text': item[1], 'confidence': item[2]} for item in texts],
            'plates': plate_verifications if plate_verifications else 'No potential plates found'
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
    app.run(host='0.0.0.0', port=5001, debug=True)
