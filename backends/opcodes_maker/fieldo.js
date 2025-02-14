'use strict';

const fieldo = {
  fd:           {msb: 11, lsb:  7, kind: 'fr', prio: 10,            dst: true, count: 0},
  fs1:          {msb: 19, lsb: 15, kind: 'fr', prio: 20,            src: true, count: 0},
  fs2:          {msb: 24, lsb: 20, kind: 'fr', prio: 30,            src: true, count: 0},
  fs3:          {msb: 31, lsb: 27, kind: 'fr', prio: 40,            src: true, count: 0},

  rd:           {msb: 11, lsb:  7, kind: 'xr', prio: 10,            dst: true, count: 753},
  rs1:          {msb: 19, lsb: 15, kind: 'xr', prio: 20,            src: true, count: 1007},
  rs2:          {msb: 24, lsb: 20, kind: 'xr', prio: 30,            src: true, count: 501},
  rs3:          {msb: 31, lsb: 27, kind: 'xr', prio: 40,            src: true, count: 26},

  rm:           {msb: 14, lsb: 12, kind: 'rm',                      count: 80},
  shamtq:       {msb: 26, lsb: 20, bits: [6, 5, 4, 3, 2, 1, 0],     count: 6},
  shamtd:       {msb: 25, lsb: 20, bits: [5, 4, 3, 2, 1, 0],        count: 17},
  shamtw:       {msb: 24, lsb: 20, bits: [4, 3, 2, 1, 0],           count: 29},
  shamtw4:      {msb: 23, lsb: 20, bits: [3, 2, 1, 0],              count: 2},

  imm12:        {msb: 31, lsb: 20, bits: [11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0], kind: 'sext', count: 23},

  imm12lo:      {msb: 11, lsb:  7, bits: [4, 3, 2, 1, 0],           count: 9},
  imm12hi:      {msb: 31, lsb: 25, bits: [11, 10, 9, 8, 7, 6, 5],   count: 12},

  imm20:        {msb: 31, lsb: 12, bits: [31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12], count: 2},
  jimm20:       {msb: 31, lsb: 12, bits: [20, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 11, 19, 18, 17, 16, 15, 14, 13, 12], count: 1},

  // vector
  vd:           {msb: 11, lsb:  7, kind: 'vr', prio: 10,            dst: true, count: 412},
  vs1:          {msb: 19, lsb: 15, kind: 'vr', prio: 40,            src: true, count: 128},
  vs2:          {msb: 24, lsb: 20, kind: 'vr', prio: 30,            src: true, count: 380},
  vs3:          {msb: 11, lsb:  7, kind: 'vr', prio: 20,            src: true, dst: true, count: 38},
  vm:           {msb: 25, lsb: 25,                                  count: 395},
  nf:           {msb: 31, lsb: 29,                                  count: 72},
  wd:           {msb: 26, lsb: 26,                                  count: 36},

  simm5:        {msb: 19, lsb: 15, bits: [4, 3, 2, 1, 0],           kind: 'sext', count: 30},
  zimm5:        {msb: 19, lsb: 15},

  fd_p:         {msb:  4, lsb:  2, kind: 'frc', prio: 10,           dst: true, count: 10},
  fs2_p:        {msb:  4, lsb:  2, kind: 'frc', prio: 30,           src: true, count: 15},
  c_fs2:        {msb:  6, lsb:  2, kind: 'fr',  prio: 30,           src: true, count: 6},

  rs1_p:        {msb:  9, lsb:  7, kind: 'xrc', prio: 20,           src: true, count: 19},
  rs2_p:        {msb:  4, lsb:  2, kind: 'xrc', prio: 30,           src: true, count: 15},
  rd_p:         {msb:  4, lsb:  2, kind: 'xrc', prio: 10,           dst: true, count: 10},
  rd_rs1_n0:    {msb: 11, lsb:  7, kind: 'xr',  prio: 10,           dst: true, src: true, count: 3},
  rd_rs1_p:     {msb:  9, lsb:  7, kind: 'xrc', prio: 10,           dst: true, src: true, count: 18},
  rd_rs1:       {msb: 11, lsb:  7, kind: 'xr',  prio: 10,           dst: true, count: 3},
  rd_n2:        {msb: 11, lsb:  7, kind: 'xr',  prio: 10,           dst: true, count: 1},
  rd_n0:        {msb: 11, lsb:  7, kind: 'xr',  prio: 10,           dst: true, count: 3},
  rs1_n0:       {msb: 11, lsb:  7, kind: 'xr',  prio: 20,           src: true, count: 1},
  c_rs2_n0:     {msb:  6, lsb:  2, kind: 'xr',  prio: 30,           src: true, count: 2},
  c_rs1_n0:     {msb: 11, lsb:  7, kind: 'xr',  prio: 20,           src: true, count: 1},
  c_rs2:        {msb:  6, lsb:  2, kind: 'xr',  prio: 30,           src: true, count: 6},
  c_sreg1:      {msb:  9, lsb:  7, kind: 'xrc', prio: 20,           src: true, count: 2},
  c_sreg2:      {msb:  4, lsb:  2, kind: 'xrc', prio: 30,           src: true, count: 2},

  aq:           {msb: 26, lsb: 26,                                  count: 22},
  rl:           {msb: 25, lsb: 25,                                  count: 22},

  // Compact Immediate Literals
  c_nzuimm10:   {msb: 12, lsb:  5, bits: [5, 4, 9, 8, 7, 6, 2, 3],  count: 1},

  c_uimm7lo:    {msb:  6, lsb:  5, bits: [2, 6],                    count: 4},
  c_uimm7hi:    {msb: 12, lsb: 10, bits: [5, 4, 3],                 count: 4},

  c_nzimm6lo:   {msb:  6, lsb:  2, bits: [4, 3, 2, 1, 0],           count: 2},
  c_nzimm6hi:   {msb: 12, lsb: 12, bits: [5],                       count: 2},

  c_imm6lo:     {msb:  6, lsb:  2, bits: [4, 3, 2, 1, 0],           count: 4},
  c_imm6hi:     {msb: 12, lsb: 12, bits: [5], kind: 'sext',         count: 4},

  c_nzimm10lo:  {msb:  6, lsb:  2, bits: [4, 6, 8, 7, 5],           count: 1},
  c_nzimm10hi:  {msb: 12, lsb: 12, bits: [9],                       count: 1},

  c_nzimm18lo:  {msb:  6, lsb:  2, bits: [16, 15, 14, 13, 12],      count: 1},
  c_nzimm18hi:  {msb: 12, lsb: 12, bits: [17],                      count: 1},

  c_imm12:      {msb: 12, lsb:  2, bits: [11, 4, 9, 8, 10, 6, 7, 3, 2, 1, 5], count: 2},

  c_bimm9lo:    {msb:  6, lsb:  2, bits: [7, 6, 2, 1, 5],           count: 2},
  c_bimm9hi:    {msb: 12, lsb: 10, bits: [8, 4, 3],                 count: 2},

  c_uimm8splo:  {msb:  6, lsb:  2, bits: [4, 3, 2, 7, 6],           count: 2},
  c_uimm8sphi:  {msb: 12, lsb: 12, bits: [5],                       count: 2},

  c_uimm8sp_s:  {msb: 12, lsb:  7, bits: [5, 4, 3, 2, 7, 6],        count: 2},

  c_nzuimm5:    {msb:  6, lsb:  2, bits: [4, 3, 2, 1, 0],           count: 2},

  c_nzuimm6lo:  {msb:  6, lsb:  2, bits: [4, 3, 2, 1, 0],           count: 4},
  c_nzuimm6hi:  {msb: 12, lsb: 12, bits: [5],                       count: 3},

  c_uimm8lo:    {msb:  6, lsb:  5, bits: [7, 6],                    count: 6},
  c_uimm8hi:    {msb: 12, lsb: 10, bits: [5, 4, 3],                 count: 6},

  c_uimm9splo:  {msb:  6, lsb:  2, bits: [4, 5, 8, 7, 6],           count: 3},
  c_uimm9sphi:  {msb: 12, lsb: 12, bits: [5],                       count: 3},

  c_uimm9sp_s:  {msb: 12, lsb:  7, bits: [5, 4, 3, 8, 7, 6],        count: 3},

  c_uimm2:      {msb:  6, lsb:  5,                                  count: 2},
  c_uimm1:      {msb:  5, lsb:  5,                                  count: 3},
  c_spimm:      {msb:  3, lsb:  2,                                  count: 4},
  c_uimm9lo:    {msb:  6, lsb:  5,                                  count: 2},
  c_uimm9hi:    {msb: 12, lsb: 10,                                  count: 2},
  c_uimm10splo: {msb:  6, lsb:  2,                                  count: 1},
  c_uimm10sphi: {msb: 12, lsb: 12,                                  count: 1},
  c_uimm10sp_s: {msb: 12, lsb:  7,                                  count: 1},
  c_index:      {msb:  9, lsb:  2,                                  count: 1},
  c_rlist:      {msb:  7, lsb:  4,                                  count: 4},

  bs:           {msb: 31, lsb: 30, count: 6}, // byte select for RV32K AES
  rnum:         {msb: 23, lsb: 20, count: 1},

  bimm12hi:     {msb: 31, lsb: 25, bits: [12, 10, 9, 8, 7, 6, 5],   count: 6},
  bimm12lo:     {msb: 11, lsb:  7, bits: [4, 3, 2, 1, 11],          count: 6},

  fm:           {msb: 31, lsb: 28, kind: 'fm',                      count: 1},
  pred:         {msb: 27, lsb: 24, kind: 'pred',                    count: 1},
  succ:         {msb: 23, lsb: 20, kind: 'succ',                    count: 1},

  csr:          {msb: 31, lsb: 20, kind: 'csr',                     count: 6},

  zimm:         {msb: 19, lsb: 15,                                  count: 6},
  zimm10:       {msb: 29, lsb: 20, kind: 'vtypei', count: 1},
  zimm11:       {msb: 30, lsb: 20, kind: 'vtypei', count: 1},

  zimm6hi:      {msb: 26, lsb: 26},
  zimm6lo:      {msb: 19, lsb: 15},

  // rv32_zpn
  imm2:         {msb: 21, lsb: 20,                                  count: 1},
  // rv_zpn
  imm3:         {msb: 22, lsb: 20,                                  count: 9},
  imm4:         {msb: 23, lsb: 20,                                  count: 8},
  imm5:         {msb: 24, lsb: 20,                                  count: 11},
  imm6:         {msb: 25, lsb: 20,                                  count: 1},

  mop_r_t_30:     {msb: 30, lsb: 30},
  mop_r_t_27_26:  {msb: 27, lsb: 26},
  mop_r_t_21_20:  {msb: 21, lsb: 20},
  mop_rr_t_30:    {msb: 30, lsb: 30},
  mop_rr_t_27_26: {msb: 27, lsb: 26},

  c_mop_t:        {msb: 10, lsb: 8},

};

module.exports = fieldo;

/* eslint camelcase: 0 */
