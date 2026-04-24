# Homebrew formula for KOPPA
#
# To publish:
#   1. Fork https://github.com/Homebrew/homebrew-core  (or create your own tap)
#   2. Replace the url/sha256 below with your actual release archive
#   3. Submit a PR — or host your own tap:
#        brew tap YOUR_USERNAME/koppa https://github.com/YOUR_USERNAME/homebrew-koppa
#        brew install koppa

class Koppa < Formula
  desc "Advanced Pentesting Domain-Specific Language"
  homepage "https://github.com/YOUR_USERNAME/koppa-lang"
  url "https://github.com/YOUR_USERNAME/koppa-lang/archive/refs/tags/v2.0.0.tar.gz"
  sha256 "REPLACE_WITH_SHA256_OF_RELEASE_TARBALL"
  license "MIT"
  head "https://github.com/YOUR_USERNAME/koppa-lang.git", branch: "main"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
    # Expose the koppa binary
    bin.install_symlink libexec/"bin/koppa"

    # Install stdlib and examples
    prefix.install "stdlib"
    prefix.install "examples"
  end

  def post_install
    ohai "KOPPA installed!"
    ohai "Try: koppa repl"
    ohai "     koppa run #{prefix}/examples/hello.kop"
  end

  test do
    assert_match "2.0.0", shell_output("#{bin}/koppa version")
    (testpath/"hello.kop").write(<<~KOP)
      import log
      log.info("brew test ok")
    KOP
    assert_match "brew test ok", shell_output("#{bin}/koppa run #{testpath}/hello.kop")
  end
end
