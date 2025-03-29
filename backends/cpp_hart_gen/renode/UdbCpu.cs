//
// Copyright (c) 2010-2024 Antmicro
//
// This file is licensed under the MIT License.
// Full license text is available in 'licenses/MIT.txt'.
//
using System;
using System.Linq;
using System.Threading;
using System.Collections.Generic;
using System.Collections.Concurrent;
using Antmicro.Renode.Core;
using Antmicro.Renode.Exceptions;
using Antmicro.Renode.Logging;
using Antmicro.Renode.Peripherals.Bus;
using Antmicro.Renode.Peripherals.CPU;
using Antmicro.Renode.Peripherals.Timers;
using Antmicro.Renode.Peripherals.CPU.Disassembler;
using Antmicro.Renode.Peripherals.CPU.Registers;
using Antmicro.Renode.Utilities;
using Antmicro.Renode.Utilities.Binding;
using Antmicro.Renode.Time;
using ELFSharp.ELF;
using ELFSharp.UImage;
using Range = Antmicro.Renode.Core.Range;
using Machine = Antmicro.Renode.Core.Machine;

namespace Antmicro.Renode.Peripherals
{
    public class UdbCpu : BaseCPU, IGPIOReceiver, ITimeSink, IDisposable
    {
        public UdbCpu(string cpuType, string sharedLibrary,
            string modelType, string configFile,
            Machine machine, Endianess endianness = Endianess.LittleEndian,
            CpuBitness bitness = CpuBitness.Bits32, uint id = 0)
            : base(id, cpuType, machine, endianness, bitness)
        {
            binder = new NativeBinder(this, sharedLibrary);
            if (renodeInit(id, modelType, configFile) < 0) {
                this.Log(LogLevel.Error, "UDB CPU initialization failed");
            }
        }

        public override void Reset()
        {
            base.Reset();
            // clear all fields defined in this class
            // clear the shared library state
        }

        public override void Dispose()
        {
            base.Dispose();
            // call any cleanup function in the shared library
            renodeDestruct();
            //after that:
            binder.Dispose();
        }

        public override string Architecture { get { return "riscv"; } }

        public void OnGPIO(int number, bool value)
        {
            // deliver the interrupt to the core

        }

        public override RegisterValue PC
        {
            get
            {
                return GetRegisterValue64(32);
            }
            set
            {
                SetRegisterValue64(32, value);
            }
        }

        public virtual void SetRegisterValue64(int register, ulong value)
        {
            // call API to set
            renodeSetRegisterValue64(register, value);
        }

        public virtual ulong GetRegisterValue64(int register)
        {
            // call API to get
            return renodeGetRegisterValue64(register);
        }

        [Export]
        public void SetTestResult(int result)
        {
            //...
            if(result == 0)
                this.Log(LogLevel.Info, "test passed");
            else
                this.Log(LogLevel.Info, "test failed");
        }

        [Export]
        public void LogCurrentPC(ulong pc)
        {
                machine.SystemBus.TryFindSymbolAt(pc, out var name, out var symbol, this);

                this.Log(LogLevel.Info, $"Entering function {name ?? "without name"} at 0x{pc.ToString("X")}");
        }

        public override ExecutionResult ExecuteInstructions(ulong numberOfInstructionsToExecute, out ulong numberOfExecutedInstructions)
        {
            instructionsExecutedThisRound = 0UL;
            ulong instructionsBefore = renodeGetIcount();
            ExecutionResult result = ExecutionResult.Ok;

            try
            {
                // call API to execute N instructions
                int udb_result = renodeExecute(numberOfInstructionsToExecute);
                if (udb_result == 1) {
                    // inst limit reached
                    result = ExecutionResult.Ok;
                } else if (udb_result == 0) {
                    // exit success
                    this.Log(LogLevel.Info, "test passed");
                    InvokeHalted(new HaltArguments(HaltReason.Abort, this));
                    return ExecutionResult.Aborted;
                } else if (udb_result == 2) {
                    // wfi
                    result = ExecutionResult.WaitingForInterrupt;
                } else if (udb_result == 3) {
                    // Pause
                    this.Log(LogLevel.Warning, "TODO: Pause");
                    InvokeHalted(new HaltArguments(HaltReason.Abort, this));
                    return ExecutionResult.Aborted;
//                    result = ExecutionResult.Pause;
                } else if (udb_result == 4) {
                    // Ebreak
                    result = ExecutionResult.StoppedAtBreakpoint;
                } else if (udb_result == -1) {
                    // Exit failure
                    this.Log(LogLevel.Warning, "test failed");
                    this.Log(LogLevel.Warning, renodeExitReason());
                    InvokeHalted(new HaltArguments(HaltReason.Abort, this));
                    return ExecutionResult.Aborted;
                } else if (udb_result == -2) {
                    // exception
                    result = ExecutionResult.Ok;
                } else if (udb_result == -3) {
                    // unpredictable behavior
                    this.Log(LogLevel.Warning, "CPU hit unpredictable behavior");
                    InvokeHalted(new HaltArguments(HaltReason.Abort, this));
                    return ExecutionResult.Aborted;
                }
            }
            catch(Exception)
            {
                this.NoisyLog("CPU exception detected, halting.");
                InvokeHalted(new HaltArguments(HaltReason.Abort, this));
                return ExecutionResult.Aborted;
            }
            finally
            {
                instructionsExecutedThisRound = instructionsBefore - renodeGetIcount();
                numberOfExecutedInstructions = instructionsExecutedThisRound;
                totalExecutedInstructions += instructionsExecutedThisRound;
            }

            this.Log(LogLevel.Info, $"Executed, {result}");

            return result;
        }

        public override ulong ExecutedInstructions => totalExecutedInstructions;

        private NativeBinder binder;

        [Import]
        private Func<uint, string, string, int> renodeInit;

        [Import]
        private Action renodeDestruct;

        [Import]
        private Func<string> renodeExitReason;

        [Import]
        private Func<ulong, int> renodeExecute;

        [Import]
        private Action<int, ulong> renodeSetRegisterValue64;

        [Import]
        private Func<int, ulong> renodeGetRegisterValue64;

        [Import]
        private Func<ulong> renodeGetIcount;

        [Export]
        protected virtual ulong ReadByteFromBus(ulong offset)
        {
            return (ulong)machine.SystemBus.ReadByte(offset, this);
        }

        [Export]
        protected virtual ulong ReadWordFromBus(ulong offset)
        {
            return (ulong)machine.SystemBus.ReadWord(offset, this);
        }

        [Export]
        protected virtual ulong ReadDoubleWordFromBus(ulong offset)
        {
            return machine.SystemBus.ReadDoubleWord(offset, this);
        }

        [Export]
        protected virtual ulong ReadQuadWordFromBus(ulong offset)
        {
            return machine.SystemBus.ReadQuadWord(offset, this);
        }

        [Export]
        protected virtual void WriteByteToBus(ulong offset, ulong value)
        {
            machine.SystemBus.WriteByte(offset, unchecked((byte)value), this);
        }

        [Export]
        protected virtual void WriteWordToBus(ulong offset, ulong value)
        {
            machine.SystemBus.WriteWord(offset, unchecked((ushort)value), this);
        }

        [Export]
        protected virtual void WriteDoubleWordToBus(ulong offset, ulong value)
        {
            machine.SystemBus.WriteDoubleWord(offset, (uint)value, this);
        }

        [Export]
        protected void WriteQuadWordToBus(ulong offset, ulong value)
        {
            machine.SystemBus.WriteQuadWord(offset, value, this);
        }

        // list of fields below is random and not verified
        private ulong registerValue;

        private bool gotRegisterValue;
        private bool setRegisterValue;
        private bool gotSingleStepMode;
        private bool gotStep;
        private ulong instructionsExecutedThisRound;
        private ulong totalExecutedInstructions;
        private bool ticksProcessed;
    }
}
