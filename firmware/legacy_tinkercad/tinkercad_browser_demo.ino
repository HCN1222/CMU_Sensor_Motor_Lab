// TINKERCAD TEXT/C++ DEMO: DC feedback below is a SOFTWARE MODEL, not the motor encoder.
// Real hardware firmware and an encoder diagnostic are supplied separately.
// Send commands ending in a semicolon, e.g. CMD,1,ARM,0;
// Never upload this simulation sketch to physical hardware.
#define SIMULATION 1
#ifndef SENSOR_MOTOR_CONTROLLER_CORE_H
#define SENSOR_MOTOR_CONTROLLER_CORE_H
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
namespace lab {
inline float limit(float x,float lo,float hi){return x<lo?lo:(x>hi?hi:x);}
inline bool finiteNumber(float x){return isfinite(x);}
inline uint32_t elapsed(uint32_t now,uint32_t then){return now-then;}
struct Config {
 float encoderCountsPerOutputRev,stepsPerOutputRev,potMaxDegrees;
 float servoMinDegrees,servoMaxDegrees,maxRpm,sensorRpm;
 float velocityKp,velocityKi,velocityKd,positionKp,positionKi,positionKd;
 uint32_t watchdogMs; bool hardwareVerified,calibrated;
 Config():encoderCountsPerOutputRev(360),stepsPerOutputRev(200),potMaxDegrees(300),servoMinDegrees(0),servoMaxDegrees(180),maxRpm(120),sensorRpm(20),velocityKp(2.2f),velocityKi(7),velocityKd(0),positionKp(0.65f),positionKi(0),positionKd(0.03f),watchdogMs(1500),hardwareVerified(false),calibrated(false){}
};
struct Debounce {
 bool stable,candidate,initialized; uint32_t candidateSince;
 Debounce():stable(false),candidate(false),initialized(false),candidateSince(0){}
 bool update(bool raw,uint32_t now,uint32_t ms){
  if(!initialized){stable=candidate=raw;candidateSince=now;initialized=true;return false;}
  if(raw!=candidate){candidate=raw;candidateSince=now;}
  if(candidate!=stable&&elapsed(now,candidateSince)>=ms){stable=candidate;return true;}return false;
 }
};
struct PID {
 float integral,previousMeasurement;bool initialized;
 PID():integral(0),previousMeasurement(0),initialized(false){}
 void reset(){integral=0;previousMeasurement=0;initialized=false;}
 float update(float target,float measured,float dt,float kp,float ki,float kd,float bound){
  if(!(dt>0))return 0;
  const float error=target-measured;
  const float derivative=initialized?-(measured-previousMeasurement)/dt:0;
  previousMeasurement=measured;initialized=true;
  const float proposed=limit(integral+error*dt,-bound/(ki>0?ki:1),bound/(ki>0?ki:1));
  const float trial=kp*error+ki*proposed+kd*derivative;
  if((trial<=bound&&trial>=-bound)||(trial>bound&&error<0)||(trial< -bound&&error>0))integral=proposed;
  return limit(kp*error+ki*integral+kd*derivative,-bound,bound);
 }
};
enum Mode{GUI=0,SENSOR=1};enum DcControl{RPM=0,POSITION=1};
struct Ack{uint32_t sequence;bool ok;const char*reason;};
// Example transfer table: replace with measured data for physical hardware.
inline float irDistanceFromAdc(int adc){
 const int raw[]={471,338,266,190,151,125,104,90,82};
 const float cm[]={10,15,20,30,40,50,60,70,80};
 if(adc>raw[0]||adc<raw[8])return -1;
 for(int i=0;i<8;++i)if(adc<=raw[i]&&adc>=raw[i+1])return cm[i]+(cm[i+1]-cm[i])*float(raw[i]-adc)/float(raw[i]-raw[i+1]);
 return 80;
}
class Controller{
public:
 Config cfg;Mode mode;DcControl dcControl;bool armed;
 float potDegrees,irRawCm,irCm,sonarCm,servoDegrees,dcDegrees,dcRpm,dcTarget,pwm;
 int32_t stepPosition,stepTarget,encoderZero;uint32_t slotCount,lastContact;bool stepPulseHigh;Debounce button,slot;
 Controller(const Config&c=Config()):cfg(c),mode(GUI),dcControl(RPM),armed(false),potDegrees(0),irRawCm(-1),irCm(-1),sonarCm(-1),servoDegrees(90),dcDegrees(0),dcRpm(0),dcTarget(0),pwm(0),stepPosition(0),stepTarget(0),encoderZero(0),slotCount(0),lastContact(0),stepPulseHigh(false),filterSum(0),filterIndex(0),filterCount(0),irRunning(false),lastControlMs(0),lastControlCounts(0),controlInitialized(false),lastStepUs(0),haveSequence(false),lastSequence(0),lastSequenceOk(false),lastSequenceReason("BOOT"),positionSettled(false){for(int i=0;i<5;++i)filter[i]=0;servoDegrees=(cfg.servoMinDegrees+cfg.servoMaxDegrees)*0.5f;}
 void stop(bool disarm=true){if(disarm)armed=false;dcControl=RPM;dcTarget=0;pwm=0;irRunning=false;stepTarget=stepPosition;stepPulseHigh=false;velocityPid.reset();positionPid.reset();positionSettled=false;}
 void setMode(Mode next);
 float stepDegrees()const{return float(stepPosition)*360/cfg.stepsPerOutputRev;}
 bool stepBusy()const{return stepPosition!=stepTarget;}
 float stepTargetDegrees()const{return float(stepTarget)*360/cfg.stepsPerOutputRev;}
 void sensors(int potAdc,int irAdc,int sonarAdc,bool slotBlocked,bool buttonPressed,uint32_t now){
  potDegrees=float(limit(potAdc,0,1023))*cfg.potMaxDegrees/1023.0f;irRawCm=irDistanceFromAdc(irAdc);
  if(irRawCm>=0){if(filterCount<5){filter[filterIndex]=irRawCm;filterSum+=irRawCm;++filterCount;}else{filterSum+=irRawCm-filter[filterIndex];filter[filterIndex]=irRawCm;}filterIndex=(filterIndex+1)%5;irCm=filterSum/filterCount;}else{irCm=-1;filterSum=0;filterCount=0;filterIndex=0;}
  sonarCm=float(sonarAdc)*(512.0f/1024.0f)*2.54f;if(sonarCm<15.24f||sonarCm>645.16f)sonarCm=-1;
  const bool slotChanged=slot.update(slotBlocked,now,10);
  if(slotChanged&&slot.stable){++slotCount;if(armed&&mode==SENSOR&&!stepBusy())moveStepper(90);}
  if(button.update(buttonPressed,now,30)&&button.stable)setMode(mode==GUI?SENSOR:GUI);
  if(armed&&mode==SENSOR){servoDegrees=cfg.servoMinDegrees+limit(potAdc,0,1023)/1023.0f*(cfg.servoMaxDegrees-cfg.servoMinDegrees);if(irCm<0||irCm<25)irRunning=false;else if(irCm>35)irRunning=true;dcControl=RPM;dcTarget=irRunning?cfg.sensorRpm:0;}
 }
 void control(uint32_t now,int32_t encoderCounts){
  if(!validConfiguration()){stop();dcDegrees=0;dcRpm=0;return;}
  dcDegrees=(float(encoderCounts)-float(encoderZero))*360/cfg.encoderCountsPerOutputRev;
  if(armed&&elapsed(now,lastContact)>cfg.watchdogMs)stop();
  if(!controlInitialized){lastControlMs=now;lastControlCounts=encoderCounts;controlInitialized=true;return;}
  const uint32_t span=elapsed(now,lastControlMs);if(span<20)return;const float dt=span*0.001f;
  const float measured=(float(encoderCounts)-float(lastControlCounts))*60/(cfg.encoderCountsPerOutputRev*dt);
  dcRpm=0.6f*dcRpm+0.4f*measured;lastControlMs=now;lastControlCounts=encoderCounts;
  if(!armed){pwm=0;return;}float targetRpm=dcTarget;
  if(dcControl==POSITION){const float error=dcTarget-dcDegrees;if(fabsf(error)<=1&&fabsf(dcRpm)<=2){pwm=0;velocityPid.reset();positionPid.reset();positionSettled=true;return;}positionSettled=false;targetRpm=positionPid.update(dcTarget,dcDegrees,dt,cfg.positionKp,cfg.positionKi,cfg.positionKd,cfg.maxRpm);}
  if(dcControl==RPM&&fabsf(targetRpm)<0.001f){pwm=0;velocityPid.reset();return;}
  pwm=velocityPid.update(targetRpm,dcRpm,dt,cfg.velocityKp,cfg.velocityKi,cfg.velocityKd,255);
 }
 int step(uint32_t nowUs){stepPulseHigh=false;if(!armed||!stepBusy())return 0;if(elapsed(nowUs,lastStepUs)<5000)return 0;lastStepUs=nowUs;const int direction=stepTarget>stepPosition?1:-1;stepPosition+=direction;stepPulseHigh=true;return direction;}
 Ack command(char*line,uint32_t now,int32_t counts);
private:
 PID velocityPid,positionPid;float filter[5],filterSum;uint8_t filterIndex,filterCount;bool irRunning;
 uint32_t lastControlMs;int32_t lastControlCounts;bool controlInitialized;uint32_t lastStepUs;bool haveSequence;uint32_t lastSequence;bool lastSequenceOk;const char*lastSequenceReason;bool positionSettled;
 bool moveStepper(float degrees){if(stepBusy())return false;const float count=degrees*cfg.stepsPerOutputRev/360;const int32_t delta=count>=0?int32_t(count+0.5f):int32_t(count-0.5f);if((delta>0&&stepPosition>INT32_MAX-delta)||(delta<0&&stepPosition<INT32_MIN-delta))return false;stepTarget=stepPosition+delta;return true;}
 static bool split(char*s,char**parts){if(!s||!*s)return false;parts[0]=s;int commas=0;for(char*p=s;*p;++p)if(*p==','){if(commas>=3)return false;*p=0;parts[++commas]=p+1;}if(commas!=3)return false;for(int i=0;i<4;++i)if(!*parts[i])return false;return true;}
 static bool parseSequence(const char*s,uint32_t&out){out=0;if(!s||!*s)return false;for(;*s;++s){if(*s<'0'||*s>'9')return false;uint8_t d=*s-'0';if(out>(UINT32_MAX-d)/10U)return false;out=out*10U+d;}return true;}
 static bool parseValue(const char*s,float&out){if(!s||!*s||*s==' '||*s=='\t')return false;char*end=0;out=float(strtod(s,&end));return end!=s&&*end==0&&finiteNumber(out);}
 Ack execute(uint32_t seq,const char*verb,float value,uint32_t now,int32_t counts);
 bool validConfiguration()const{return finiteNumber(cfg.encoderCountsPerOutputRev)&&cfg.encoderCountsPerOutputRev>0&&finiteNumber(cfg.stepsPerOutputRev)&&cfg.stepsPerOutputRev>0&&cfg.stepsPerOutputRev<=100000&&finiteNumber(cfg.potMaxDegrees)&&cfg.potMaxDegrees>0&&finiteNumber(cfg.servoMinDegrees)&&finiteNumber(cfg.servoMaxDegrees)&&cfg.servoMinDegrees>=0&&cfg.servoMaxDegrees>cfg.servoMinDegrees&&finiteNumber(cfg.maxRpm)&&cfg.maxRpm>0&&cfg.maxRpm<=10000&&finiteNumber(cfg.sensorRpm)&&fabsf(cfg.sensorRpm)<=cfg.maxRpm&&cfg.watchdogMs>0;}
};
}
#endif
void lab::Controller::setMode(lab::Mode next){stop(false);mode=next;}
lab::Ack lab::Controller::command(char*line,uint32_t now,int32_t counts){
  uint32_t seq=0;float value=0;char*parts[4];
  if(!split(line,parts)||strcmp(parts[0],"CMD")||!parseSequence(parts[1],seq)||!parseValue(parts[3],value))return Ack{seq,false,"FORMAT"};
  if(haveSequence&&int32_t(seq-lastSequence)<=0){if(seq==lastSequence)return Ack{seq,lastSequenceOk,lastSequenceReason};return Ack{seq,false,"STALE_SEQ"};}
  Ack ack=execute(seq,parts[2],value,now,counts);haveSequence=true;lastSequence=seq;lastSequenceOk=ack.ok;lastSequenceReason=ack.reason;if(ack.ok)lastContact=now;return ack;
 }
lab::Ack lab::Controller::execute(uint32_t seq,const char*verb,float value,uint32_t now,int32_t counts){
  const Ack ok={seq,true,"OK"};
  if(!strcmp(verb,"STOP")){if(value!=0)return Ack{seq,false,"RANGE"};stop();return ok;}
  if(!strcmp(verb,"PING"))return value==0?ok:Ack{seq,false,"RANGE"};
  if(!strcmp(verb,"ARM")){if(value!=0)return Ack{seq,false,"RANGE"};if(!validConfiguration())return Ack{seq,false,"CONFIG_INVALID"};if(!cfg.hardwareVerified)return Ack{seq,false,"CONFIG_REQUIRED"};if(!armed){stop();armed=true;lastContact=now;}return ok;}
  if(!strcmp(verb,"MODE")){if(value!=0&&value!=1)return Ack{seq,false,"RANGE"};setMode(value==0?GUI:SENSOR);return ok;}
  if(!strcmp(verb,"ZERO")){if(value!=0)return Ack{seq,false,"RANGE"};if(armed)return Ack{seq,false,"DISARM_FIRST"};encoderZero=counts;dcDegrees=0;stepPosition=stepTarget=0;slotCount=0;return ok;}
  const bool servo=!strcmp(verb,"SERVO"),rpm=!strcmp(verb,"DC_RPM"),move=!strcmp(verb,"DC_MOVE"),stepMove=!strcmp(verb,"STEP_MOVE");
  if(!servo&&!rpm&&!move&&!stepMove)return Ack{seq,false,"UNKNOWN_COMMAND"};if(!armed)return Ack{seq,false,"DISARMED"};if(mode!=GUI)return Ack{seq,false,"SENSOR_MODE"};
  if(servo){if(value<cfg.servoMinDegrees||value>cfg.servoMaxDegrees)return Ack{seq,false,"RANGE"};servoDegrees=value;}
  else if(rpm){if(fabsf(value)>cfg.maxRpm)return Ack{seq,false,"RANGE"};dcControl=RPM;dcTarget=value;velocityPid.reset();positionPid.reset();}
  else if(move){if(fabsf(value)>3600)return Ack{seq,false,"RANGE"};dcDegrees=(float(counts)-float(encoderZero))*360/cfg.encoderCountsPerOutputRev;dcControl=POSITION;dcTarget=dcDegrees+value;velocityPid.reset();positionPid.reset();}
  else{if(fabsf(value)>3600)return Ack{seq,false,"RANGE"};if(!moveStepper(value))return Ack{seq,false,"BUSY_OR_LIMIT"};}return ok;
 }
#include <Servo.h>
#define SYNTHETIC_DC_FEEDBACK 1
const uint8_t POT_PIN=A0,IR_PIN=A1,SONAR_PIN=A2,SLOT_PIN=A3,BUTTON_PIN=A4;
const uint8_t ENC_A=2,ENC_B=3,DC_PWM=5,DC_IN1=4,DC_IN2=7;
const uint8_t SERVO_PIN=9,STEP_PIN=6,DIR_PIN=8,ENABLE_PIN=10,MODE_LED=13;
const bool SLOT_BLOCKED_HIGH=true;
const float MEASURED_ENCODER_COUNTS_PER_REV=360.0f; // Tinkercad placeholder: verify against independent motor RPM.
const int8_t ENCODER_SIGN=-1;
lab::Config makeConfig(){lab::Config c;c.hardwareVerified=true;c.calibrated=false;c.encoderCountsPerOutputRev=MEASURED_ENCODER_COUNTS_PER_REV;c.watchdogMs=30000;return c;}
lab::Controller controller(makeConfig());Servo servo;
volatile int32_t encoderCounts=0;volatile uint8_t previousEncoderBits=0;
float modelPosition=0,modelRpm=0;uint32_t modelLastMs=0;
char inputLine[80];uint8_t inputLength=0;bool droppingLine=false;
uint32_t lastSensorsMs=0,lastTelemetryMs=0;int potRaw=0,irRaw=0,sonarRaw=0;bool slotBlocked=false;
void encoderChanged(){const uint8_t bits=(digitalRead(ENC_A)<<1)|digitalRead(ENC_B);const int8_t transition[16]={0,-1,1,0,1,0,0,-1,-1,0,0,1,0,1,-1,0};encoderCounts+=ENCODER_SIGN*transition[(previousEncoderBits<<2)|bits];previousEncoderBits=bits;}
int32_t readEncoder(){
#if SYNTHETIC_DC_FEEDBACK
 return int32_t(modelPosition);
#else
 noInterrupts();const int32_t value=encoderCounts;interrupts();return value;
#endif
}
void updateSoftwareModel(uint32_t now){
#if SYNTHETIC_DC_FEEDBACK
 if(!modelLastMs){modelLastMs=now;return;}const float dt=lab::limit(lab::elapsed(now,modelLastMs)*0.001f,0,0.1f);modelLastMs=now;
 const float desired=controller.armed?controller.pwm*0.55f:0;modelRpm+=(desired-modelRpm)*dt/(0.12f+dt);
 if(!controller.armed)modelRpm=0;modelPosition+=modelRpm*dt*controller.cfg.encoderCountsPerOutputRev/60.0f;
#endif
}
void reportAck(const lab::Ack&ack){Serial.print(F("ACK,"));Serial.print(ack.sequence);Serial.print(',');Serial.print(ack.ok?F("OK,"):F("ERR,"));Serial.println(ack.reason);}
void readCommands(uint32_t now){for(uint8_t budget=0;budget<48&&Serial.available();++budget){char c=Serial.read();if(c=='\r')continue;if(c=='\n'||c==';'){if(droppingLine)Serial.println(F("ACK,0,ERR,LINE_TOO_LONG"));else if(inputLength){inputLine[inputLength]=0;reportAck(controller.command(inputLine,now,readEncoder()));}inputLength=0;droppingLine=false;}else if(!droppingLine){if(c<32||c>126||inputLength>=sizeof(inputLine)-1){droppingLine=true;inputLength=0;}else inputLine[inputLength++]=c;}}}
void state(uint32_t now){
 Serial.print(F("STATE,"));Serial.print(now);Serial.print(',');Serial.print(int(controller.mode));Serial.print(',');Serial.print(controller.potDegrees,2);Serial.print(',');Serial.print(controller.irRawCm,2);Serial.print(',');Serial.print(controller.irCm,2);Serial.print(',');Serial.print(controller.sonarCm,2);Serial.print(',');Serial.print(controller.slotCount);Serial.print(',');Serial.print(controller.servoDegrees,2);Serial.print(',');Serial.print(controller.dcDegrees,2);Serial.print(',');Serial.print(controller.dcRpm,2);Serial.print(',');Serial.print(controller.dcTarget,2);Serial.print(',');Serial.print(controller.dcControl==lab::RPM?F("RPM"):F("POSITION"));Serial.print(',');Serial.print(controller.stepDegrees(),2);Serial.print(',');Serial.print(controller.stepBusy()?1:0);Serial.print(',');Serial.print(controller.armed?1:0);Serial.print(',');Serial.println(controller.cfg.calibrated?1:0);
 Serial.print(F("RAW,"));Serial.print(now);Serial.print(',');Serial.print(potRaw);Serial.print(',');Serial.print(irRaw);Serial.print(',');Serial.print(sonarRaw);Serial.print(',');Serial.println(slotBlocked?1:0);
}
void driveMotor(){const float output=controller.armed?controller.pwm:0;const int magnitude=int(lab::limit(fabsf(output),0,255));const int8_t direction=output>0?1:(output<0?-1:0);static int8_t previousDirection=0;if(direction!=previousDirection){analogWrite(DC_PWM,0);digitalWrite(DC_IN1,direction>0?HIGH:LOW);digitalWrite(DC_IN2,direction<0?HIGH:LOW);previousDirection=direction;}analogWrite(DC_PWM,magnitude);}
void setup(){
 pinMode(DC_PWM,OUTPUT);pinMode(DC_IN1,OUTPUT);pinMode(DC_IN2,OUTPUT);pinMode(STEP_PIN,OUTPUT);pinMode(DIR_PIN,OUTPUT);pinMode(ENABLE_PIN,OUTPUT);pinMode(MODE_LED,OUTPUT);digitalWrite(STEP_PIN,LOW);digitalWrite(ENABLE_PIN,HIGH);analogWrite(DC_PWM,0);pinMode(SLOT_PIN,INPUT_PULLUP);pinMode(BUTTON_PIN,INPUT_PULLUP);pinMode(ENC_A,INPUT_PULLUP);pinMode(ENC_B,INPUT_PULLUP);previousEncoderBits=(digitalRead(ENC_A)<<1)|digitalRead(ENC_B);attachInterrupt(digitalPinToInterrupt(ENC_A),encoderChanged,CHANGE);attachInterrupt(digitalPinToInterrupt(ENC_B),encoderChanged,CHANGE);Serial.begin(115200);Serial.println(F("INFO,SOFTWARE_DC_FEEDBACK_NOT_ENCODER"));
}
void loop(){
 const uint32_t now=millis();updateSoftwareModel(now);readCommands(now);
 if(lab::elapsed(now,lastSensorsMs)>=20){lastSensorsMs=now;potRaw=analogRead(POT_PIN);irRaw=analogRead(IR_PIN);sonarRaw=analogRead(SONAR_PIN);slotBlocked=(digitalRead(SLOT_PIN)==(SLOT_BLOCKED_HIGH?HIGH:LOW));controller.sensors(potRaw,irRaw,sonarRaw,slotBlocked,digitalRead(BUTTON_PIN)==LOW,now);}
 controller.control(now,readEncoder());driveMotor();
 if(controller.armed){if(!servo.attached())servo.attach(SERVO_PIN);servo.write(int(controller.servoDegrees+0.5f));}else if(servo.attached())servo.detach();
 digitalWrite(ENABLE_PIN,controller.armed?LOW:HIGH);const int stepDirection=controller.step(micros());if(stepDirection){digitalWrite(DIR_PIN,stepDirection>0?HIGH:LOW);delayMicroseconds(2);digitalWrite(STEP_PIN,HIGH);delayMicroseconds(3);digitalWrite(STEP_PIN,LOW);}digitalWrite(MODE_LED,controller.mode==lab::SENSOR?HIGH:LOW);if(lab::elapsed(now,lastTelemetryMs)>=100){lastTelemetryMs=now;state(now);}
}
