# typed: true

# since we generate Architecture methods with metaprogramming, we need an explicit interface for
# Sorbet

class Architecture
  sig { params(name: String).returns(Csr) }
  def csr(name); end

  sig { returns(T::Array[Csr]) }
  def csrs; end

  sig { returns(T::Array[Instruction]) }
  def instructions; end

  sig { params(name: String).returns(Instruction) }
  def instruction(name); end

  sig { params(name: String).returns(Extension) }
  def extension(name); end
end
