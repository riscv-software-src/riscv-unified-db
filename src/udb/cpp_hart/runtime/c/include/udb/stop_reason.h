#pragma once

typedef struct _StopReason {
  static const int ExitSuccess = 0;            // Guest program exited successfully (only occurs with certain tracers)
  static const int InstLimitReached = 1;       // Normal exit from run_one/run_bb/run_n
  static const int Wfi = 2;                    // Executed WFI
  static const int Pause = 3;                  // Executed PAUSE
  static const int Ebreak = 4;                 // Executed EBREAK
  static const int ExitFailure = -1;           // Guest program exited with failure (only occurs with certain tracers)
  static const int Exception = -2;             // Hit exception while in run_one/run_bb/run_n
  static const int UnpredictableBehavior = -3; // Hart tried to do something that is unpredictable according to the standard/config
} StopReason;
