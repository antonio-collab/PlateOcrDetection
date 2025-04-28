#include <WiFi.h>
#include <WiFiClient.h>
#include <HTTPClient.h>
#include "esp_camera.h"

const char* ssid = "IFMA_VISITANTE";
const char* password = "visitante@ifma";
const char* serverUrl = "http://10.24.8.239:5001/upload";

#define CAMERA_MODEL_AI_THINKER
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
#define flash 4

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  Serial.print("Conectando ao Wi-Fi");
  int timeout = 0;
  while (WiFi.status() != WL_CONNECTED && timeout < 20) {
    delay(500);
    Serial.print(".");
    timeout++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nConectado ao Wi-Fi!");
  } else {
    Serial.println("\nFalha ao conectar ao Wi-Fi.");
    return;
  }

  // Inicializa a câmera
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 4;
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("O início da câmera falhou com erro 0x%x", err);
    delay(1000);
    ESP.restart();
  }

  camera_fb_t *fb = esp_camera_fb_get();
  if (fb) {
    Serial.println("Foto capturada");
  } else {
    Serial.println("Erro ao capturar imagem");
    return;
  }

  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    client.setTimeout(5000);

    if (client.connect("10.24.8.239", 5001)) {
      String boundary = "----ESP32Boundary";
      String contentType = "multipart/form-data; boundary=" + boundary;
      String formDataStart = "--" + boundary + "\r\n" +
                             "Content-Disposition: form-data; name=\"image\"; filename=\"image.jpg\"\r\n" +
                             "Content-Type: image/jpeg\r\n\r\n";
      String formDataEnd = "\r\n--" + boundary + "--\r\n";

      client.print("POST /upload HTTP/1.1\r\n");
      client.print("Host: 10.24.8.239\r\n");
      client.print("Content-Type: " + contentType + "\r\n");
      client.print("Content-Length: " + String(formDataStart.length() + fb->len + formDataEnd.length()) + "\r\n");
      client.print("Connection: close\r\n\r\n");

      client.print(formDataStart);
      client.write(fb->buf, fb->len);
      client.print(formDataEnd);

      Serial.println("Requisição enviada. Aguardando resposta...");

      while (client.connected() || client.available()) {
        if (client.available()) {
          String response = client.readString();
          Serial.println("Resposta HTTP:");
          Serial.println(response);
          break;
        }
      }

      client.stop();
    } else {
      Serial.println("Falha ao conectar ao servidor");
    }
  }

  if (fb) {
    esp_camera_fb_return(fb);
  }
}

void loop() {
}
