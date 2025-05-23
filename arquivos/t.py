from flask import Flask, jsonify, request, url_for, send_from_directory
import os
from werkzeug.utils import secure_filename
from loguru import logger
import cv2
import requests
import easyocr
import re

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

    def read_text_from_image(self, image_path, decoder='beamsearch'):
        results = self.reader.readtext(image_path, decoder=decoder)
        logger.info(f'OCR results: {results}')  # Log dos resultados do OCR
        return results

    def filter_plates(self, results):
        potential_plates = []
        for result in results:
            text, confidence = result[1], result[2]
            logger.info(f'Extracted text: {text} | Confidence: {confidence}')
            # Verifica se a placa tem a estrutura válida e o texto tem um nível de confiança suficiente
            if confidence > 0.6 and len(text) >= 7 and is_valid_mercosul_plate(text):
                potential_plates.append({
                    'text': text,
                    'confidence': confidence
                })
        return potential_plates if potential_plates else None

# Função de verificação de placa Mercosul
def is_valid_mercosul_plate(plate):
    """
    Verifica se a placa segue o formato da placa Mercosul.
    A placa Mercosul deve ter:
    - 3 letras seguidas de 4 números ou 4 números seguidos de 3 letras
    - Não pode ter letras I, O, Q.
    """
    # Remove espaços e verifica se o comprimento é 7 caracteres
    plate = plate.replace(" ", "").upper()
    
    if len(plate) != 7:
        return False
    
    # Verifica se a placa contém letras e números de forma válida
    # O formato pode ser: 3 letras + 4 números ou 4 números + 3 letras
    if re.match(r'^[A-Z]{3}[0-9]{4}$', plate) or re.match(r'^[0-9]{4}[A-Z]{3}$', plate):
        # Verifica se contém letras I, O ou Q
        if any(char in plate for char in "IOQ"):
            return False
        return True
    return False

# Função para verificar a placa no Adonis js
def check_plate_in_database(plate):
    try:
        logger.info(f'Verificando placa: {plate}')  # Log da placa sendo verificada
        response = requests.get(f'http://localhost:3555/search-plate?plate={plate}')
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f'Resposta da API para a placa {plate}: {data}')
            
            if 'message' in data and data['message'] == 'Placa cadastrada':
                logger.info(f'Placa {plate} cadastrada na API.')
                return True
            else:
                logger.warning(f'Placa {plate} não foi cadastrada ou resposta inesperada: {data}')
                return False
        else:
            logger.error(f'Erro ao verificar a placa. Status code: {response.status_code}')
            return False
    except requests.Timeout:
        logger.error(f'Timeout ao tentar verificar a placa {plate}.')
        return False
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
        texts = plate_analysis.read_text_from_image(file_path, 'beamsearch')
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
