/*
  ESP32 传感器节点示例固件
  通过 MQTT 向亿界上报数据

  硬件：ESP32-DevKitC + PIR / 门磁 / 温湿度传感器
  依赖库：
    - PubSubClient by Nick O'Leary
    - DHT sensor library by Adafruit（可选）

  MQTT Topic: ynex/sensor/<location>/<device_type>/<device_id>

  配置：修改下面的 WIFI_SSID / WIFI_PASSWORD / MQTT_SERVER / LOCATION / DEVICE_TYPE / DEVICE_ID
*/

#include <WiFi.h>
#include <PubSubClient.h>

// ========== 用户配置 ==========
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_SERVER = "192.168.1.100";  // Y·NEX 服务器或 MQTT Broker IP
const int MQTT_PORT = 1883;
const char* CLIENT_ID = "esp32_sensor_001";

const char* LOCATION = "living_room";
const char* DEVICE_TYPE = "pir";  // pir / door / mmwave / temp_humi
const char* DEVICE_ID = "001";
// ==============================

char topic[128];
WiFiClient espClient;
PubSubClient client(espClient);

const int PIR_PIN = 13;   // 人体红外引脚
const int DOOR_PIN = 14;  // 门磁引脚（低电平=关，高电平=开）

unsigned long lastReconnectAttempt = 0;
unsigned long lastReport = 0;

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("WiFi connected");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
}

boolean reconnect() {
  if (client.connect(CLIENT_ID)) {
    Serial.println("MQTT connected");
  }
  return client.connected();
}

void publishState(const char* state, float value = NAN, int battery = -1) {
  if (!client.connected()) return;

  char payload[256];
  char timeStr[32];
  // 简单时间戳
  snprintf(timeStr, sizeof(timeStr), "%lu", millis());

  if (!isnan(value) && battery >= 0) {
    snprintf(payload, sizeof(payload),
             "{\"state\":\"%s\",\"value\":%.2f,\"battery\":%d,\"timestamp\":%s}",
             state, value, battery, timeStr);
  } else if (!isnan(value)) {
    snprintf(payload, sizeof(payload),
             "{\"state\":\"%s\",\"value\":%.2f,\"timestamp\":%s}",
             state, value, timeStr);
  } else if (battery >= 0) {
    snprintf(payload, sizeof(payload),
             "{\"state\":\"%s\",\"battery\":%d,\"timestamp\":%s}",
             state, battery, timeStr);
  } else {
    snprintf(payload, sizeof(payload),
             "{\"state\":\"%s\",\"timestamp\":%s}",
             state, timeStr);
  }

  client.publish(topic, payload);
  Serial.print("Published to ");
  Serial.print(topic);
  Serial.print(": ");
  Serial.println(payload);
}

void setup() {
  Serial.begin(115200);
  snprintf(topic, sizeof(topic), "jarvis/sensor/%s/%s/%s", LOCATION, DEVICE_TYPE, DEVICE_ID);

  pinMode(PIR_PIN, INPUT);
  pinMode(DOOR_PIN, INPUT_PULLUP);

  setup_wifi();
  client.setServer(MQTT_SERVER, MQTT_PORT);
}

void loop() {
  if (!client.connected()) {
    unsigned long now = millis();
    if (now - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = now;
      if (reconnect()) {
        lastReconnectAttempt = 0;
      }
    }
  } else {
    client.loop();
  }

  // PIR 检测：检测到人体时上报
  if (strcmp(DEVICE_TYPE, "pir") == 0) {
    static bool lastPirState = false;
    bool pirState = digitalRead(PIR_PIN) == HIGH;
    if (pirState != lastPirState) {
      lastPirState = pirState;
      publishState(pirState ? "detected" : "clear");
    }
  }

  // 门磁检测：状态变化时上报
  if (strcmp(DEVICE_TYPE, "door") == 0) {
    static bool lastDoorState = false;
    bool doorOpen = digitalRead(DOOR_PIN) == LOW;  // 根据接线调整
    if (doorOpen != lastDoorState) {
      lastDoorState = doorOpen;
      publishState(doorOpen ? "open" : "close");
    }
  }

  // 每 60 秒心跳一次
  unsigned long now = millis();
  if (now - lastReport > 60000) {
    lastReport = now;
    if (client.connected()) {
      // 发送当前状态作为心跳
      if (strcmp(DEVICE_TYPE, "pir") == 0) {
        publishState(digitalRead(PIR_PIN) == HIGH ? "detected" : "clear");
      } else if (strcmp(DEVICE_TYPE, "door") == 0) {
        publishState(digitalRead(DOOR_PIN) == LOW ? "open" : "close");
      }
    }
  }

  delay(100);
}
