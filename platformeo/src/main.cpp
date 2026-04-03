#include <Arduino.h>
#include <Adafruit_TinyUSB.h>   // Required for nRF52840 with newer Arduino core
#include <nrf.h>

// ==================== CONFIGURATION ====================
#define CHANNEL_START       0
#define CHANNEL_END         80
#define DELAY_MS            6
#define SAMPLES_PER_CHANNEL 4
#define SPECTRUM_RADIO_MODE RADIO_MODE_MODE_Nrf_1Mbit
// ======================================================

uint32_t get_frequency(uint8_t channel) {
  return 2400 + channel;
}

int8_t measure_average_rssi(uint8_t channel) {
  // Disable radio if it was active
  NRF_RADIO->TASKS_DISABLE = 1;
  while (NRF_RADIO->EVENTS_DISABLED == 0) {}
  NRF_RADIO->EVENTS_DISABLED = 0;

  // Configure radio for RSSI measurement
  NRF_RADIO->MODE = SPECTRUM_RADIO_MODE;
  NRF_RADIO->FREQUENCY = channel;

  NRF_RADIO->PCNF0 = (8UL << RADIO_PCNF0_LFLEN_Pos);
  NRF_RADIO->PCNF1 = (RADIO_PCNF1_WHITEEN_Disabled << RADIO_PCNF1_WHITEEN_Pos) |
                     (RADIO_PCNF1_ENDIAN_Big << RADIO_PCNF1_ENDIAN_Pos) |
                     (3UL << RADIO_PCNF1_BALEN_Pos) |
                     (0UL << RADIO_PCNF1_STATLEN_Pos) |
                     (255UL << RADIO_PCNF1_MAXLEN_Pos);

  NRF_RADIO->CRCCNF = RADIO_CRCCNF_LEN_Disabled;

  // Enable receiver
  NRF_RADIO->TASKS_RXEN = 1;
  while (NRF_RADIO->EVENTS_READY == 0) {}
  NRF_RADIO->EVENTS_READY = 0;

  NRF_RADIO->TASKS_START = 1;
  delay(2);

  // Take multiple samples and calculate average
  int32_t sum = 0;
  for (int i = 0; i < SAMPLES_PER_CHANNEL; i++) {
    NRF_RADIO->EVENTS_RSSIEND = 0;
    NRF_RADIO->TASKS_RSSISTART = 1;
    while (NRF_RADIO->EVENTS_RSSIEND == 0) {}
    sum += (int8_t)NRF_RADIO->RSSISAMPLE;
    delayMicroseconds(100);
  }

  // Disable radio
  NRF_RADIO->TASKS_DISABLE = 1;
  while (NRF_RADIO->EVENTS_DISABLED == 0) {}
  NRF_RADIO->EVENTS_DISABLED = 0;

  return (int8_t)(sum / SAMPLES_PER_CHANNEL);
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);

  Serial.begin(921600);

  // Long wait with LED blinking (helps with some boards)
  unsigned long start = millis();
  while (!Serial && (millis() - start < 4500)) {
    digitalWrite(LED_BUILTIN, (millis() % 80 < 40) ? HIGH : LOW);
    delay(10);
  }
  digitalWrite(LED_BUILTIN, LOW);

  delay(300);

  // Start high-frequency clock
  NRF_CLOCK->TASKS_HFCLKSTART = 1;
  while (NRF_CLOCK->EVENTS_HFCLKSTARTED == 0) {}

  // Print frequency header (for Python script compatibility)
  for (uint8_t ch = CHANNEL_START; ch <= CHANNEL_END; ch++) {
    Serial.print(get_frequency(ch));
    if (ch < CHANNEL_END) Serial.print(" ");
  }
  Serial.println();

  Serial.println("=== nRF52840 Spectrum Analyzer READY (TinyUSB) ===");
  Serial.flush();
}

void loop() {
  Serial.print(millis());
  Serial.print(": ");

  for (uint8_t ch = CHANNEL_START; ch <= CHANNEL_END; ch++) {
    int8_t rssi = measure_average_rssi(ch);
    Serial.print(rssi);
    if (ch < CHANNEL_END) Serial.print(" ");
    delay(DELAY_MS);
  }
  Serial.println();
  Serial.flush();
}