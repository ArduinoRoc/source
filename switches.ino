#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

#define SERVOMIN  150 // this is the 'minimum' pulse length count (out of 4096)
#define SERVOMAX  500 // this is the 'maximum' pulse length count (out of 4096)

void setup() {
  Serial.begin(115200);
  Serial.println("Switch controller.");
  pinMode(8, OUTPUT);
  digitalWrite(8, LOW);
  pinMode(9, OUTPUT);
  digitalWrite(9, LOW);
  pinMode(7, OUTPUT);
  digitalWrite(7, LOW);
  pinMode(6, OUTPUT);
  digitalWrite(6, LOW);
  pinMode(5, OUTPUT);
  digitalWrite(5, LOW);
  pinMode(4, OUTPUT);
  digitalWrite(4, LOW);
  pinMode(3, OUTPUT);
  digitalWrite(3, LOW);
  pinMode(2, OUTPUT);
  digitalWrite(2, LOW);

  pwm.begin();
  pwm.setPWMFreq(60);  // This is the maximum PWM frequency
}

void loop() {
  String cmd;
  if (Serial.available() > 0) {
    cmd = Serial.readStringUntil('\n');
    cmd.trim();
    String id;
    String angle; 
    String switchtype;
    int k = 0;
    for (int i=0; i<cmd.length(); i = i+1){
      char x = cmd[i];
      // First position:
      if(k == 0){
        if(x == ','){
          k += 1;
        } else {
          id += x;
        }
      // Second position (angle):
      } else if(k == 1){
        if(x == ','){
          k += 1;
        } else {
          angle += x;
        }
      // Last position:
      } else {
        switchtype += x;
      }
    }
    if (switchtype == "servo"){
      pwm.setPWM(String(id).toInt(), 0, angleToPulse(String(angle).toInt()));
    } else {
      Serial.println("Relay");
      if(angle == "low"){
        Serial.println("Switching high to low to high");
        digitalWrite(String(id).toInt(), LOW);
        delay(50);
        digitalWrite(String(id).toInt(), HIGH);
      } else if(angle == "high"){
        Serial.println("Switching low to high to low");
        digitalWrite(String(id).toInt(), HIGH);
        delay(50);
        digitalWrite(String(id).toInt(), LOW);
      }
    }
  }
}

/*
 * angleToPulse(int ang)
 * gets angle in degree and returns the pulse width
 * also prints the value on seial monitor
 * written by Ahmad Nejrabi for Robojax, Robojax.com
 */
int angleToPulse(int ang){
   int pulse = map(ang,0, 180, SERVOMIN, SERVOMAX);// map angle of 0 to 180 to Servo min and Servo max 
   Serial.print("Angle: ");Serial.print(ang);
   Serial.print(" pulse: ");Serial.println(pulse);
   return pulse;
}
