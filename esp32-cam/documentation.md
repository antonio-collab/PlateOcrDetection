# Documentação do Projeto: Sistema de Reconhecimento de Placas com ESP32-CAM e Flask

Este projeto implementa um sistema automatizado de reconhecimento de placas utilizando o **ESP32-CAM** como dispositivo de captura de imagem e um servidor local desenvolvido em **Python** com o framework **Flask** para realizar o processamento OCR (Reconhecimento Óptico de Caracteres) e a verificação das placas.

## Descrição Geral

O sistema é composto por:
- Um **ESP32-CAM**, responsável pela captura da imagem e envio da mesma via Wi-Fi para o servidor.
- Um **servidor Flask**, que recebe a imagem, processa utilizando a biblioteca **EasyOCR**, realiza a detecção de texto, e verifica se a placa está cadastrada.
- Um banco de dados (simulado via API) que armazena as placas autorizadas.

## Fluxo de Funcionamento

1. O **ESP32-CAM** captura uma imagem quando um veículo é detectado.
2. A imagem é enviada ao servidor Flask via requisição HTTP POST no formato `multipart/form-data`.
3. O servidor Flask recebe a imagem, armazena temporariamente e realiza o processamento OCR com a biblioteca **EasyOCR**.
4. Os textos detectados são filtrados para identificar placas potenciais.
5. O servidor consulta uma API de verificação de placas e retorna a resposta ao ESP32-CAM.

## Requisitos

### Hardware
- **ESP32-CAM** (modelo AI-Thinker)
- Acesso a uma rede Wi-Fi

### Software
- **Arduino IDE** (para programar o ESP32-CAM)

## Configuração do ESP32-CAM

### **Conexão Wi-Fi e Inicialização da Câmera**
O código abaixo configura o ESP32-CAM para conectar-se a uma rede Wi-Fi e inicializar a câmera:

```cpp
#include <WiFi.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include "esp_camera.h"

const char* ssid = "SEU_SSID";
const char* password = "SUA_SENHA";

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("Conectado ao Wi-Fi!");

  // Inicializa a câmera (configuração omitida para brevidade)
}
```

### **Envio da Imagem ao Servidor**
A imagem capturada é enviada ao servidor utilizando o formato `multipart/form-data`:

```cpp
WiFiClient client;
if (client.connect("192.168.1.130", 5000)) {
  String boundary = "----ESP32Boundary";
  String formDataStart = "--" + boundary + "\r\n" +
                         "Content-Disposition: form-data; name=\"image\"; filename=\"image.jpg\"\r\n" +
                         "Content-Type: image/jpeg\r\n\r\n";
  String formDataEnd = "\r\n--" + boundary + "--\r\n";

  client.print("POST /upload HTTP/1.1\r\n");
  client.print("Host: 192.168.1.130\r\n");
  client.print("Content-Type: multipart/form-data; boundary=" + boundary + "\r\n");
  client.print("Content-Length: " + String(formDataStart.length() + fb->len + formDataEnd.length()) + "\r\n");
  client.print("Connection: close\r\n\r\n");

  client.print(formDataStart);
  client.write(fb->buf, fb->len);
  client.print(formDataEnd);
}
```


## Exemplo de Resposta do Servidor

Quando uma imagem é enviada com sucesso e processada, o servidor retorna uma resposta JSON contendo os textos detectados:

```json
{
  "detected_texts": [
    [
      [10, 20, 100, 200],
      "ABC1234",
      0.95
    ]
  ]
}
```