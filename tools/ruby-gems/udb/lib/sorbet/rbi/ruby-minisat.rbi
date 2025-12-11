# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear


module MiniSat
  class Literal
  end
  class Variable
    sig { returns(Literal) }
    def +@; end

    sig { returns(Literal) }
    def -@; end

    sig { returns(T::Boolean) }
    def value; end
  end
  class Solver
    sig { params(term: T.any(Variable, Literal, T::Array[T.any(Variable, Literal)])).returns(Solver) }
    def <<(term); end

    sig { returns(Variable) }
    def new_var; end

    sig { params(v: T.any(Variable, Literal)).returns(Solver) }
    def add_clause(*v); end

    sig { params(v: Variable).returns(T::Boolean) }
    def [](v); end

    sig { returns(T::Boolean) }
    def solve; end

    sig { returns(T::Boolean) }
    def simplify; end

    sig { returns(T::Boolean) }
    def simplify_db; end

    sig { returns(Integer) }
    def var_size; end

    sig { returns(Integer) }
    def clause_size; end

    sig { override.returns(String) }
    def to_s; end

    sig { returns(T::Boolean) }
    def solved?; end

    sig { returns(T::Boolean) }
    def satisfied?; end
  end
end
