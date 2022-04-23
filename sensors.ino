int detectPins[] = {
52, 50, 48, 46, 44, 42, 40, 38, 36, 25, 32, 30, 28, 26, 24, 22, 53, 51, 23};
int sensorCount = 19; 

void setup() {
  for (int Pin = 0; Pin < sensorCount; Pin++) {
    pinMode(detectPins[Pin], INPUT); 
  }
  Serial.begin(115200);
}

void loop() {
  float sums[sensorCount];
  for (int Pin = 0; Pin < sensorCount; Pin++) {
    sums[Pin] = 0;
  }
  for (int x = 0; x < 1000; x++) {
    for (int Pin = 0; Pin < sensorCount; Pin++) {
      sums[Pin] = sums[Pin] + digitalRead(detectPins[Pin]);
      delay(0.1);
      }
  }

  for (int Pin = 0; Pin < sensorCount; Pin++) {
    Serial.print(sums[Pin] / 100 < 9);
    if(Pin < sensorCount-1){
      Serial.print(",");
    } else{
      Serial.println("");
    }
  }
  delay(75);
}
