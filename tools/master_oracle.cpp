// Oracle : mesures de RicchBeatz Master (Source/Dsp.h, sans JUCE) sur un fichier brut.
// Entrée : float32 entrelacé stéréo. Usage : master_oracle fichier.f32 fs
// Sortie : "integrated lra true_peak_dbtp"
// Compilation : g++ -O2 -std=c++17 -I <Master-plugin>/Source tools/master_oracle.cpp -o data/bin/master_oracle
#include "Dsp.h"
#include <cstdio>
#include <cstdlib>
#include <vector>

int main (int argc, char** argv)
{
    if (argc < 3) { std::fprintf (stderr, "usage: master_oracle file.f32 fs\n"); return 1; }
    FILE* f = std::fopen (argv[1], "rb");
    if (! f) { std::fprintf (stderr, "lecture impossible\n"); return 2; }
    std::vector<float> inter;
    float buf[8192];
    size_t got;
    while ((got = std::fread (buf, sizeof (float), 8192, f)) > 0) inter.insert (inter.end(), buf, buf + got);
    std::fclose (f);
    const int n = (int) (inter.size() / 2);
    std::vector<float> L ((size_t) n), R ((size_t) n);
    for (int i = 0; i < n; ++i) { L[(size_t) i] = inter[(size_t) (2 * i)]; R[(size_t) i] = inter[(size_t) (2 * i + 1)]; }
    const double fs = std::atof (argv[2]);
    const auto loud = master::measureLoudness (L.data(), R.data(), n, fs);
    const float tp = master::truePeakLinear (L.data(), R.data(), n);
    std::printf ("%.4f %.4f %.4f\n", loud.integrated, loud.lra, 20.0 * std::log10 (std::max (tp, 1.0e-9f)));
    return 0;
}
