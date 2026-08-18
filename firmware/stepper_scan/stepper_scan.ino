// =====================================================================
// FIRMWARE STEPPER SCAN (Arduino 1) + FORWARD FREKUENSI KE LASER
// =====================================================================
// Board ini mengendalikan:
//   1. Motor stepper X & Y (raster zig-zag + jog manual)
//   2. Fan pendingin (ON saat motor bergerak, OFF saat diam/sampling)
//   3. Waktu diam BREAK_TIME di setiap titik sampling
//   4. Meneruskan perintah frekuensi laser ke Arduino 2
//
// Laptop ↔ Arduino 1 (USB Serial 115200) — Python / Serial Monitor
// Arduino 1 TX (pin 1) → Arduino 2 RX (pin 0), GND bersama
//   (pin TX hardware yang sama dipakai USB ke laptop; f= diulang ke Serial
//    agar keluar di pin 1 menuju Arduino laser)
// Arduino 2: USB hanya tegangan; modulasi di firmware/laser_modulasi
//
// Perintah frekuensi dari Python / Serial Monitor:
//   f=17000
// diteruskan ke Arduino laser sebagai "f=17000\n" (baud 115200).
//
// CATATAN SINKRONISASI PYTHON (backend/config.py + frontend):
//   POINT_DISTANCE_CM, ROW_DISTANCE_CM, STEP_PER_CM_X/Y,
//   JOG_STEP_DELAY, STEP_DELAY, BREAK_TIME, DEFAULT_BAUDRATE
//   WAJIB SAMA dengan konstanta Python.
// =====================================================================


// =====================================================================
// 1. KONFIGURASI PIN MOTOR + FAN
// =====================================================================

#define PIN_X_STEP 2
#define PIN_X_DIR  5

#define PIN_Y_STEP 3
#define PIN_Y_DIR  6

#define PIN_ENABLE 8

#define PIN_FAN 7


// =====================================================================
// 2. ARAH MOTOR
// =====================================================================

#define X_DIR_KANAN HIGH
#define X_DIR_KIRI  LOW

#define Y_DIR_TURUN HIGH
#define Y_DIR_NAIK  LOW


// =====================================================================
// 3. KALIBRASI MOTOR
// =====================================================================

#define STEP_PER_CM_X 1000.0
#define STEP_PER_CM_Y 1000.0


// =====================================================================
// 4. AREA SCAN
// =====================================================================

float scanLengthCm = 0.0;
float scanHeightCm = 0.0;


// =====================================================================
// 5. PARAMETER RASTER
// =====================================================================

#define POINT_DISTANCE_CM 0.05
#define ROW_DISTANCE_CM   0.05


// =====================================================================
// 6. KECEPATAN DAN WAKTU
// =====================================================================

#define STEP_DELAY 800

// Lama motor DIAM di setiap titik sampling -- Python merekam pada jendela ini.
#define BREAK_TIME 1000

#define JOG_STEP_DELAY 300
#define STOP_CHECK_INTERVAL_STEP 20
#define MAX_JOG_STEPS 2000000UL
#define STOP_CHECK_INTERVAL_MS 20


// =====================================================================
// 7. VARIABEL GLOBAL
// =====================================================================

int jumlahTitikPerBaris;
int jumlahBaris;

bool sedangScanning = false;
bool sedangJog = false;
bool stopRequested = false;


// =====================================================================
// 8. KONDISI FAN
// =====================================================================

void kondisiBergerak() {
  digitalWrite(PIN_FAN, HIGH);
}

void kondisiDiam() {
  digitalWrite(PIN_FAN, LOW);
}

void kondisiJog() {
  digitalWrite(PIN_FAN, HIGH);
}

void kondisiIdle() {
  digitalWrite(PIN_FAN, LOW);
}


// =====================================================================
// 8b. KIRIM FREKUENSI KE ARDUINO LASER
// =====================================================================

void kirimFrekuensiKeLaser(float hz) {
  // Keluar lewat TX pin 1 → Arduino 2 RX, sekaligus terbaca di Serial Monitor / Python.
  Serial.print(F("f="));
  Serial.println(hz, 2);
  Serial.print(F("Frekuensi laser dikirim ke Arduino 2 (TX->RX): "));
  Serial.print(hz);
  Serial.println(F(" Hz"));
}


// =====================================================================
// 9. SETUP
// =====================================================================

void setup() {
  Serial.begin(115200);

  pinMode(PIN_ENABLE, OUTPUT);
  digitalWrite(PIN_ENABLE, HIGH);  // disable dulu

  pinMode(PIN_X_STEP, OUTPUT);
  digitalWrite(PIN_X_STEP, LOW);
  pinMode(PIN_X_DIR, OUTPUT);
  digitalWrite(PIN_X_DIR, LOW);

  pinMode(PIN_Y_STEP, OUTPUT);
  digitalWrite(PIN_Y_STEP, LOW);
  pinMode(PIN_Y_DIR, OUTPUT);
  digitalWrite(PIN_Y_DIR, LOW);

  pinMode(PIN_FAN, OUTPUT);
  digitalWrite(PIN_FAN, LOW);

  digitalWrite(PIN_ENABLE, LOW);  // aktifkan driver

  tampilkanMenu();
}


// =====================================================================
// 10. LOOP
// =====================================================================

void loop() {
  if (Serial.available() > 0) {
    String perintah = Serial.readStringUntil('\n');
    perintah.trim();
    perintah.toLowerCase();
    if (perintah.length() == 0) {
      return;
    }
    prosesPerintahSerial(perintah);
  }
}


// =====================================================================
// 11. MENU SERIAL
// =====================================================================

void tampilkanMenu() {
  Serial.println();
  Serial.println(F("=== FIRMWARE STEPPER SCAN (+ forward laser) ==="));
  Serial.println();
  Serial.println(F("Perintah:"));
  Serial.println(F("  x=10       -> panjang area scan"));
  Serial.println(F("  y=10       -> lebar area scan"));
  Serial.println(F("  start      -> mulai scanning"));
  Serial.println(F("  f=17000    -> kirim frekuensi modulasi ke Arduino laser"));
  Serial.println(F("  kanan      -> JOG X kanan"));
  Serial.println(F("  kiri       -> JOG X kiri"));
  Serial.println(F("  maju       -> JOG Y maju"));
  Serial.println(F("  mundur     -> JOG Y mundur"));
  Serial.println(F("  stop       -> hentikan scanning/JOG"));
  Serial.println();
  Serial.print(F("X saat ini = "));
  Serial.print(scanLengthCm);
  Serial.println(F(" cm"));
  Serial.print(F("Y saat ini = "));
  Serial.print(scanHeightCm);
  Serial.println(F(" cm"));
  Serial.print(F("BREAK_TIME = "));
  Serial.print(BREAK_TIME);
  Serial.println(F(" ms"));
  Serial.println(F("Laser link: TX pin 1 -> Arduino2 RX pin 0 @ 115200"));
  Serial.println(F("------------------------------------"));
}


// =====================================================================
// 12. PROSES PERINTAH SERIAL
// =====================================================================

void prosesPerintahSerial(String perintah) {
  // f= hanya saat idle (bukan tengah scan/jog).
  if (sedangScanning || sedangJog) {
    if (perintah == "stop") {
      // ditangani di cekPerintahStop saat scan; di sini hanya saat idle setelah selesai
      Serial.println(F("Sedang scanning/JOG. Gunakan 'stop'."));
      return;
    }
    Serial.println(F("Sedang scanning/JOG. Gunakan 'stop'."));
    return;
  }

  if (perintah.startsWith("x=")) {
    float nilai = perintah.substring(2).toFloat();
    if (nilai > 0) {
      scanLengthCm = nilai;
      Serial.print(F("X diset menjadi "));
      Serial.print(scanLengthCm);
      Serial.println(F(" cm"));
    } else {
      Serial.println(F("Nilai X tidak valid."));
    }
  }
  else if (perintah.startsWith("y=")) {
    float nilai = perintah.substring(2).toFloat();
    if (nilai > 0) {
      scanHeightCm = nilai;
      Serial.print(F("Y diset menjadi "));
      Serial.print(scanHeightCm);
      Serial.println(F(" cm"));
    } else {
      Serial.println(F("Nilai Y tidak valid."));
    }
  }
  else if (perintah.startsWith("f=")) {
    float nilai = perintah.substring(2).toFloat();
    if (nilai >= 0.1 && nilai <= 50000.0) {
      kirimFrekuensiKeLaser(nilai);
    } else {
      Serial.println(F("Nilai frekuensi tidak valid (0.1 .. 50000 Hz)."));
    }
  }
  else if (perintah == "start") {
    mulaiScanning();
  }
  else if (perintah == "kanan") {
    jalankanJog(F("KANAN (X+)"), true, X_DIR_KANAN);
  }
  else if (perintah == "kiri") {
    jalankanJog(F("KIRI (X-)"), true, X_DIR_KIRI);
  }
  else if (perintah == "maju") {
    jalankanJog(F("MAJU (Y+)"), false, Y_DIR_TURUN);
  }
  else if (perintah == "mundur") {
    jalankanJog(F("MUNDUR (Y-)"), false, Y_DIR_NAIK);
  }
  else if (perintah == "stop") {
    Serial.println(F("Tidak sedang scanning/JOG."));
  }
  else if (perintah == "menu") {
    tampilkanMenu();
  }
  else {
    Serial.println(F("Perintah tidak dikenali."));
  }
}


// =====================================================================
// 13. CEK PERINTAH STOP
// =====================================================================

void cekPerintahStop() {
  if (Serial.available() > 0) {
    String perintah = Serial.readStringUntil('\n');
    perintah.trim();
    perintah.toLowerCase();
    if (perintah == "stop") {
      stopRequested = true;
      Serial.println(F("Perintah STOP diterima."));
    }
  }
}


// =====================================================================
// 14. MULAI SCANNING
// =====================================================================

void mulaiScanning() {
  jumlahTitikPerBaris =
    (int)round(scanLengthCm / POINT_DISTANCE_CM) + 1;
  jumlahBaris =
    (int)round(scanHeightCm / ROW_DISTANCE_CM) + 1;

  Serial.println(F("------------------------------------"));
  Serial.print(F("Mulai scanning X = "));
  Serial.print(scanLengthCm);
  Serial.print(F(" cm, Y = "));
  Serial.print(scanHeightCm);
  Serial.println(F(" cm"));
  Serial.print(F("Jumlah titik per baris = "));
  Serial.println(jumlahTitikPerBaris);
  Serial.print(F("Jumlah baris = "));
  Serial.println(jumlahBaris);
  Serial.print(F("BREAK_TIME = "));
  Serial.print(BREAK_TIME);
  Serial.println(F(" ms"));

  stopRequested = false;
  sedangScanning = true;

  rasterScan();

  sedangScanning = false;
  kondisiIdle();

  if (stopRequested) {
    Serial.println(F("Scanning DIHENTIKAN."));
    stopRequested = false;
  } else {
    Serial.println(F("Scanning selesai."));
  }

  tampilkanMenu();
}


// =====================================================================
// 15. KONVERSI CM KE STEP
// =====================================================================

long cmToStepX(float cm) {
  return (long)round(cm * STEP_PER_CM_X);
}

long cmToStepY(float cm) {
  return (long)round(cm * STEP_PER_CM_Y);
}


// =====================================================================
// 16. GERAK MOTOR X / Y SAAT SCANNING
// =====================================================================

void moveX(float cm, int arah) {
  long jumlahStep = cmToStepX(cm);
  digitalWrite(PIN_X_DIR, arah);
  kondisiBergerak();

  for (long i = 0; i < jumlahStep; i++) {
    if (i % STOP_CHECK_INTERVAL_STEP == 0) {
      cekPerintahStop();
      if (stopRequested) {
        return;
      }
    }
    digitalWrite(PIN_X_STEP, HIGH);
    delayMicroseconds(STEP_DELAY);
    digitalWrite(PIN_X_STEP, LOW);
    delayMicroseconds(STEP_DELAY);
  }
}

void moveY(float cm, int arah) {
  long jumlahStep = cmToStepY(cm);
  digitalWrite(PIN_Y_DIR, arah);
  kondisiBergerak();

  for (long i = 0; i < jumlahStep; i++) {
    if (i % STOP_CHECK_INTERVAL_STEP == 0) {
      cekPerintahStop();
      if (stopRequested) {
        return;
      }
    }
    digitalWrite(PIN_Y_STEP, HIGH);
    delayMicroseconds(STEP_DELAY);
    digitalWrite(PIN_Y_STEP, LOW);
    delayMicroseconds(STEP_DELAY);
  }
}


// =====================================================================
// 17. JOG MOTOR
// =====================================================================

void jogX(int arah) {
  digitalWrite(PIN_X_DIR, arah);
  for (unsigned long i = 0; i < MAX_JOG_STEPS; i++) {
    if (i % STOP_CHECK_INTERVAL_STEP == 0) {
      cekPerintahStop();
      if (stopRequested) {
        return;
      }
    }
    digitalWrite(PIN_X_STEP, HIGH);
    delayMicroseconds(JOG_STEP_DELAY);
    digitalWrite(PIN_X_STEP, LOW);
    delayMicroseconds(JOG_STEP_DELAY);
  }
}

void jogY(int arah) {
  digitalWrite(PIN_Y_DIR, arah);
  for (unsigned long i = 0; i < MAX_JOG_STEPS; i++) {
    if (i % STOP_CHECK_INTERVAL_STEP == 0) {
      cekPerintahStop();
      if (stopRequested) {
        return;
      }
    }
    digitalWrite(PIN_Y_STEP, HIGH);
    delayMicroseconds(JOG_STEP_DELAY);
    digitalWrite(PIN_Y_STEP, LOW);
    delayMicroseconds(JOG_STEP_DELAY);
  }
}

void jalankanJog(const __FlashStringHelper* namaArah, bool sumbuX, int arahPin) {
  stopRequested = false;
  sedangJog = true;

  Serial.print(F("Jog "));
  Serial.println(namaArah);

  kondisiJog();

  if (sumbuX) {
    jogX(arahPin);
  } else {
    jogY(arahPin);
  }

  kondisiIdle();
  sedangJog = false;
  stopRequested = false;
  Serial.println(F("Jog berhenti."));
}


// =====================================================================
// 18. PAUSE / SAMPLING (motor diam, fan OFF -- laser di Arduino lain)
// =====================================================================

void pauseSampling() {
  kondisiDiam();

  unsigned long mulai = millis();
  unsigned long lastCheck = mulai;

  while ((millis() - mulai) < BREAK_TIME) {
    unsigned long sekarang = millis();
    if ((sekarang - lastCheck) >= STOP_CHECK_INTERVAL_MS) {
      lastCheck = sekarang;
      cekPerintahStop();
      if (stopRequested) {
        return;
      }
    }
  }
}


// =====================================================================
// 19. RASTER SCAN ZIG-ZAG
// =====================================================================

void rasterScan() {
  for (int baris = 1; baris <= jumlahBaris; baris++) {
    if (stopRequested) {
      return;
    }

    // Pesan ini dipakai Python untuk sinkronisasi ulang jadwal per baris.
    Serial.print(F("Scanning baris ke-"));
    Serial.println(baris);

    bool bergerakKeKanan = (baris % 2 == 1);
    int arahX = bergerakKeKanan ? X_DIR_KANAN : X_DIR_KIRI;

    // Titik pertama baris: diam + sampling window
    pauseSampling();
    if (stopRequested) {
      return;
    }

    for (int titik = 2; titik <= jumlahTitikPerBaris; titik++) {
      moveX(POINT_DISTANCE_CM, arahX);
      if (stopRequested) {
        return;
      }

      pauseSampling();
      if (stopRequested) {
        return;
      }
    }

    if (baris < jumlahBaris) {
      moveY(ROW_DISTANCE_CM, Y_DIR_TURUN);
      if (stopRequested) {
        return;
      }
    }
  }
}
