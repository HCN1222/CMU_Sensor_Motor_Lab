// TEMPORARY TINKERCAD-ONLY DIAGNOSTIC. Do not upload to physical hardware.
// Starts the model automatically at PWM80, stops at10s, restarts at12s,
// and stops permanently at22s. No servo/stepper control and no PID.
// Restore the main sketch after recording the result.
volatile unsigned long edgesA=0,edgesB=0;
void countA(){++edgesA;}
void countB(){++edgesB;}
int lastPhase=-1;
unsigned long lastPrint=0;
void setup(){
  Serial.begin(115200);
  pinMode(2,INPUT_PULLUP);pinMode(3,INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(2),countA,CHANGE);
  attachInterrupt(digitalPinToInterrupt(3),countB,CHANGE);
  pinMode(4,OUTPUT);pinMode(7,OUTPUT);pinMode(5,OUTPUT);
  digitalWrite(4,HIGH);digitalWrite(7,LOW);
  analogWrite(5,80);lastPhase=0;
  Serial.println("DIAGNOSTIC,ms,phase,AB,edgesA,edgesB");
}
void loop(){
  unsigned long now=millis();
  int phase=now<10000?0:(now<12000?1:(now<22000?2:3));
  if(phase!=lastPhase){analogWrite(5,(phase==0||phase==2)?80:0);lastPhase=phase;}
  if(now-lastPrint>=200){
    lastPrint=now;
    noInterrupts();unsigned long a=edgesA,b=edgesB;interrupts();
    Serial.print(now);Serial.print(',');Serial.print(phase);Serial.print(',');
    Serial.print(digitalRead(2));Serial.print(digitalRead(3));Serial.print(',');
    Serial.print(a);Serial.print(',');Serial.println(b);
  }
}
