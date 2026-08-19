// ======================================================
// MODULASI LASER (Timer1 + perintah f= dari Arduino 1)
// Arduino UNO / NANO
// D9 = output laser (OC1A — square wave hardware, duty 50%)
//
// Wiring (Arduino 2 = board ini):
//   Arduino1 pin 10 (SoftSerial TX) → Arduino2 pin 8 (SoftSerial RX)
//   GND Arduino1 ↔ GND Arduino2  (wajib)
//   USB Arduino2: cukup tegangan
//
// PENTING: JANGAN pakai pin 0 (hardware RX) untuk link ini —
// pin 0 bentrok chip USB, sehingga perintah f=2 sering gagal
// dan laser tetap di frekuensi default.
//
// Perintah (baud 9600):
//   f=2 / f=17000     → set frekuensi + nyalakan modulasi
//   laser=on / laser=1  → nyalakan modulasi (frekuensi terakhir)
//   laser=off / laser=0 → matikan laser (pin D9 LOW) — uji PA vs noise
// Frekuensi valid: ~0.12 Hz .. 50000 Hz (Timer1); 2 Hz OK.
// ======================================================

#include <SoftwareSerial.h>

#define LASER_PIN 9

// SoftSerial perintah dari Arduino 1 (bukan hardware Serial/USB)
#define PIN_CMD_RX 8
#define PIN_CMD_TX 7   // tidak dipakai (TX mengambang OK)
#define LASER_LINK_BAUD 9600

SoftwareSerial cmdSerial(PIN_CMD_RX, PIN_CMD_TX);

// ======================================================
// FREKUENSI DEFAULT (Hz) — sampai perintah f= datang
// ======================================================
#define LASER_MOD_FREQ_HZ 17000.0

// Timer1 @ 16 MHz, prescaler max 1024 → f_min ≈ 0.119 Hz
#define FREQ_MIN_HZ 0.12
#define FREQ_MAX_HZ 50000.0


float frequency = LASER_MOD_FREQ_HZ;
bool useHardwareTimer = false;
bool laserEnabled = true;   // false = D9 diam LOW (uji noise tanpa laser)
bool laserState = false;
unsigned long halfPeriodUs = 1;
unsigned long lastToggleUs = 0;

String serialBuf;


void laserOffSoftware()
{
  digitalWrite(LASER_PIN, LOW);
  laserState = false;
}


void stopTimer1()
{
  TCCR1A = 0;
  TCCR1B = 0;
  OCR1A = 0;
  useHardwareTimer = false;
  pinMode(LASER_PIN, OUTPUT);
  laserOffSoftware();
}


// Square wave di pin 9 via Timer1 CTC + toggle OC1A.
// f = F_CPU / (2 * N * (OCR1A + 1))
bool startTimer1(float hz)
{
  const uint16_t presc[] = {1, 8, 64, 256, 1024};
  const uint8_t csBits[] = {1, 2, 3, 4, 5};

  for (uint8_t i = 0; i < 5; i++)
  {
    double counts = (double)F_CPU / (2.0 * (double)presc[i] * (double)hz);
    if (counts >= 2.0 && counts <= 65536.0)
    {
      uint16_t ocr = (uint16_t)(counts - 1.0 + 0.5);

      // Pastikan pin 9 output sebelum mengaktifkan OC1A
      pinMode(LASER_PIN, OUTPUT);

      TCCR1A = 0;
      TCCR1B = 0;
      TCNT1 = 0;
      OCR1A = ocr;
      // CTC (WGM12), toggle OC1A (COM1A0)
      TCCR1A = _BV(COM1A0);
      TCCR1B = _BV(WGM12) | csBits[i];

      useHardwareTimer = true;
      return true;
    }
  }
  return false;
}


void updateFrequencySoftware()
{
  halfPeriodUs = (unsigned long)(500000.0 / frequency);
  if (halfPeriodUs < 1UL)
    halfPeriodUs = 1UL;
  lastToggleUs = micros();
}


void matikanLaser()
{
  laserEnabled = false;
  stopTimer1();
}


void terapkanFrekuensi(float hz)
{
  if (hz < FREQ_MIN_HZ)
    hz = FREQ_MIN_HZ;
  if (hz > FREQ_MAX_HZ)
    hz = FREQ_MAX_HZ;

  frequency = hz;
  laserEnabled = true;

  stopTimer1();

  if (startTimer1(frequency))
  {
    // Modulasi digenerate hardware — loop tidak perlu toggle.
    return;
  }

  // Fallback sangat jarang (di luar rentang Timer1)
  updateFrequencySoftware();
}


void nyalakanLaser()
{
  laserEnabled = true;
  terapkanFrekuensi(frequency);
}


void prosesPerintah(String perintah)
{
  perintah.trim();
  perintah.toLowerCase();
  if (perintah.length() == 0)
    return;

  if (perintah == "laser=off" || perintah == "laser=0")
  {
    matikanLaser();
    return;
  }

  if (perintah == "laser=on" || perintah == "laser=1")
  {
    nyalakanLaser();
    return;
  }

  if (perintah.startsWith("f="))
  {
    float nilai = perintah.substring(2).toFloat();
    if (nilai >= FREQ_MIN_HZ && nilai <= FREQ_MAX_HZ)
    {
      terapkanFrekuensi(nilai);
    }
  }
}


void bacaPerintahNonBlocking()
{
  while (cmdSerial.available() > 0)
  {
    char c = (char)cmdSerial.read();
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
    else
    {
      serialBuf = "";
    }
  }
}


void setup()
{
  pinMode(LASER_PIN, OUTPUT);
  laserOffSoftware();

  cmdSerial.begin(LASER_LINK_BAUD);

  terapkanFrekuensi(LASER_MOD_FREQ_HZ);
}


void loop()
{
  bacaPerintahNonBlocking();

  if (!laserEnabled)
  {
    // Laser mati: pastikan pin diam (stopTimer1 sudah LOW).
    return;
  }

  if (useHardwareTimer)
  {
    // Square wave sudah dijalankan Timer1 di pin 9.
    return;
  }

  // Fallback software (hampir tidak terpakai untuk 0.12..50 kHz)
  unsigned long now = micros();
  if ((unsigned long)(now - lastToggleUs) >= halfPeriodUs)
  {
    lastToggleUs = now;
    laserState = !laserState;
    digitalWrite(LASER_PIN, laserState ? HIGH : LOW);
  }
}
