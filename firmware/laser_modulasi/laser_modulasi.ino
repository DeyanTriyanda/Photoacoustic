// ======================================================
// MODULASI LASER (OTOMATIS + FREKUENSI DARI ARDUINO 1)
// Arduino UNO / NANO
// D9 = output laser
//
// Wiring (Arduino 2 = board ini):
//   Arduino1 pin 10 (SoftSerial TX) → Arduino2 pin 0 (RX)
//   GND Arduino1 ↔ GND Arduino2  (wajib — ground bersama)
//   USB Arduino2: cukup tegangan (data ke laptop tidak dipakai)
//
// Saat upload ke board ini: lepaskan dulu kabel ke pin 0 (RX).
//
// Frekuensi default: LASER_MOD_FREQ_HZ di bawah.
// Frekuensi baru dari Arduino 1: baris Serial "f=17000"
// (baud SoftSerial link = 9600 — samakan dengan stepper).
//
// Begitu bertegangan, modulasi LANGSUNG berjalan (duty 50%).
// Samakan default dengan TARGET_FREQ_HZ di backend/config.py.
// ======================================================

#define LASER_PIN 9

// Baud link SoftSerial dari Arduino stepper (bukan USB ke PC)
#define LASER_LINK_BAUD 9600

// ======================================================
// FREKUENSI DEFAULT (Hz) — dipakai sampai perintah f= datang
// Contoh: 2.0 / 10.0 / 100.0 / 1000.0 / 17000.0
// ======================================================
#define LASER_MOD_FREQ_HZ 17000.0

#define FREQ_MIN_HZ 0.1
#define FREQ_MAX_HZ 50000.0


float frequency = LASER_MOD_FREQ_HZ;
bool laserState = false;
unsigned long halfPeriodUs = 1;
unsigned long lastToggleUs = 0;

String serialBuf;


void updateFrequency()
{
  if (frequency < FREQ_MIN_HZ)
    frequency = FREQ_MIN_HZ;
  if (frequency > FREQ_MAX_HZ)
    frequency = FREQ_MAX_HZ;

  halfPeriodUs = (unsigned long)(500000.0 / frequency);

  if (halfPeriodUs < 1)
    halfPeriodUs = 1;
}


void laserOff()
{
  digitalWrite(LASER_PIN, LOW);
  laserState = false;
}


void terapkanFrekuensi(float hz)
{
  frequency = hz;
  updateFrequency();
  lastToggleUs = micros();
}


void prosesPerintah(String perintah)
{
  perintah.trim();
  perintah.toLowerCase();
  if (perintah.length() == 0)
    return;

  if (perintah.startsWith("f="))
  {
    float nilai = perintah.substring(2).toFloat();
    if (nilai >= FREQ_MIN_HZ && nilai <= FREQ_MAX_HZ)
    {
      terapkanFrekuensi(nilai);
    }
  }
}


void bacaSerialNonBlocking()
{
  while (Serial.available() > 0)
  {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r')
    {
      if (serialBuf.length() > 0)
      {
        prosesPerintah(serialBuf);
        serialBuf = "";
      }
    }
    else if (serialBuf.length() < 48)
    {
      serialBuf += c;
    }
  }
}


void setup()
{
  pinMode(LASER_PIN, OUTPUT);
  laserOff();

  // Hardware Serial RX (pin 0) menerima SoftSerial dari Arduino 1 pin 10
  Serial.begin(LASER_LINK_BAUD);

  frequency = LASER_MOD_FREQ_HZ;
  updateFrequency();
  lastToggleUs = micros();
}


void loop()
{
  bacaSerialNonBlocking();

  // Modulasi kontinu selama Arduino bertegangan.
  unsigned long now = micros();

  if ((unsigned long)(now - lastToggleUs) >= halfPeriodUs)
  {
    lastToggleUs = now;

    laserState = !laserState;

    digitalWrite(
      LASER_PIN,
      laserState ? HIGH : LOW
    );
  }
}
