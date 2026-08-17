// ======================================================
// MODULASI LASER (frekuensi via Serial 0 .. 20000 Hz)
// Arduino UNO / NANO
// D9 = output laser
//
// Saat bertegangan: modulasi mulai dengan LASER_MOD_FREQ_HZ default.
// Python mengirim:  f=17000
//   -> frekuensi diganti live (tanpa upload ulang).
// Batas: 0.1 Hz .. 20000 Hz. Di luar itu ditolak + pesan error.
//
// Samakan nilai UI Frekuensi Target dengan yang dikirim ke board ini.
// ======================================================

#define LASER_PIN 9

// Default saat boot (boleh diganti; UI/Python akan menimpa via Serial)
#define LASER_MOD_FREQ_HZ 17000.0
#define LASER_FREQ_MIN_HZ 0.1
#define LASER_FREQ_MAX_HZ 20000.0

float frequency = LASER_MOD_FREQ_HZ;
bool laserState = false;
unsigned long halfPeriodUs = 1;
unsigned long lastToggleUs = 0;

String serialBuf;


void updateFrequency()
{
  if (frequency < LASER_FREQ_MIN_HZ)
    frequency = LASER_FREQ_MIN_HZ;
  if (frequency > LASER_FREQ_MAX_HZ)
    frequency = LASER_FREQ_MAX_HZ;

  halfPeriodUs = (unsigned long)(500000.0 / frequency);
  if (halfPeriodUs < 1)
    halfPeriodUs = 1;
}


void laserOff()
{
  digitalWrite(LASER_PIN, LOW);
  laserState = false;
}


void applyFrequency(float freq)
{
  if (freq < LASER_FREQ_MIN_HZ || freq > LASER_FREQ_MAX_HZ)
  {
    Serial.print("ERR freq di luar 0.1..20000 Hz: ");
    Serial.println(freq);
    return;
  }
  frequency = freq;
  updateFrequency();
  lastToggleUs = micros();
  Serial.print("OK Frequency = ");
  Serial.print(frequency);
  Serial.print(" Hz | Half period = ");
  Serial.print(halfPeriodUs);
  Serial.println(" us");
}


void handleSerialLine(String line)
{
  line.trim();
  line.toLowerCase();
  if (line.length() == 0)
    return;

  // Format: f=17000  atau  freq=17000
  if (line.startsWith("f="))
  {
    applyFrequency(line.substring(2).toFloat());
    return;
  }
  if (line.startsWith("freq="))
  {
    applyFrequency(line.substring(5).toFloat());
    return;
  }

  Serial.print("ERR perintah tidak dikenali: ");
  Serial.println(line);
}


void setup()
{
  pinMode(LASER_PIN, OUTPUT);
  laserOff();

  Serial.begin(115200);
  delay(50);

  frequency = LASER_MOD_FREQ_HZ;
  updateFrequency();
  lastToggleUs = micros();

  Serial.println();
  Serial.println("=== MODULASI LASER (Serial) ===");
  Serial.print("Default Frequency = ");
  Serial.print(frequency);
  Serial.println(" Hz");
  Serial.println("Kirim: f=17000  (rentang 0.1 .. 20000 Hz)");
  Serial.println();
}


void loop()
{
  // Baca perintah Serial (non-blocking per karakter)
  while (Serial.available() > 0)
  {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r')
    {
      if (serialBuf.length() > 0)
      {
        handleSerialLine(serialBuf);
        serialBuf = "";
      }
    }
    else if (serialBuf.length() < 64)
    {
      serialBuf += c;
    }
  }

  // Modulasi kontinu
  unsigned long now = micros();
  if ((unsigned long)(now - lastToggleUs) >= halfPeriodUs)
  {
    lastToggleUs = now;
    laserState = !laserState;
    digitalWrite(LASER_PIN, laserState ? HIGH : LOW);
  }
}
