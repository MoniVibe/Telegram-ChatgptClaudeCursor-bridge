High-Level Directive: Vector EM, Non-Paraxial, Modular Compute-Shader App
Scope

Full vector Maxwell propagation. No paraxial or thin-lens approximations. Free-space and in-medium propagation via exact vector angular-spectrum (including evanescent waves). Interface transitions via Stratton–Chu surface integrals on the true lens surfaces. Sum complex electric fields from all sources. Output intensities and detector image.

Inputs

source_map: image. Nonzero pixels are point sources. Per-pixel:

amplitude A

initial phase φ

polarization unit vector p̂ (encode as RGB or separate map)

z of source plane

lambda_nm and bandwidth_nm (FWHM). Spectral density S(λ) selectable (Gaussian/ measured CSV).

coherence:

spatial: coherent | incoherent | partial(mode_decomp)

temporal: coherent | incoherent

detector: {pixels_x, pixels_y, pitch_m, z_m}

lenses[]: each lens has

pose {x,y,z, rx,ry,rz}

material dispersion n(λ) (Sellmeier or table)

surfaces: triangulated meshes S1, S2 in lens local frame

optional helper: {aperture_radius_m, f_m at λ0} → if meshes omitted, auto-generate spherical surfaces consistent with f_m, radius, n(λ0) (ray-exact, not thin-lens)

apertures[]: absorbing stops as meshes or binary masks at known z

domain: {extent_x_m, extent_y_m, Nxy} per sampled plane

units: SI

Outputs

Field snapshots: complex E(x,y,z) or per-plane magnitude/phase

Volume or slice intensities: I(x,y,z)=|E|^2

Detector image I_det(u,v)

Diagnostics: energy balance, polarization maps, mode counts, aliasing margins

Physics Baseline

Time-harmonic fields per λ: 
∇
×
∇
×
𝐸
−
𝑘
2
𝜀
𝑟
𝐸
=
0
∇×∇×E−k
2
ε
r
	​

E=0, 
𝑘
=
2
𝜋
/
𝜆
k=2π/λ

Vector angular-spectrum in homogeneous medium:

2D FFT → 
𝐸
~
(
𝑘
𝑥
,
𝑘
𝑦
,
𝑧
)
E
~
(k
x
	​

,k
y
	​

,z)

Enforce transversality with projector 
𝑃
(
𝑘
)
=
𝐼
−
𝑘
𝑘
⊤
∣
𝑘
∣
2
P(k)=I−
∣k∣
2
kk
⊤
	​


Propagate exactly: 
𝐸
~
(
𝑧
+
Δ
𝑧
)
=
𝑃
(
𝑘
)
𝐸
~
(
𝑧
)
 
𝑒
𝑖
𝑘
𝑧
Δ
𝑧
E
~
(z+Δz)=P(k)
E
~
(z)e
ik
z
	​

Δz

𝑘
𝑧
=
(
𝑛
𝑘
0
)
2
−
𝑘
𝑥
2
−
𝑘
𝑦
2
k
z
	​

=
(nk
0
	​

)
2
−k
x
2
	​

−k
y
2
	​

	​

 (pure imaginary for evanescent; retain decay)

Curved interfaces (lens surfaces) via vector Huygens/Stratton–Chu on triangulated surface S:

Equivalent currents: 
𝐽
𝑠
=
𝑛
×
𝐻
J
s
	​

=n×H, 
𝑀
𝑠
=
−
𝑛
×
𝐸
M
s
	​

=−n×E

Field in target medium using dyadic Green’s function 
𝐺
‾
‾
G
. Implement quadrature over triangles. Handles refraction and vector coupling exactly. No thin-lens phase masks.

Inside lens: propagate in homogeneous n(λ) volumes between the two surfaces using vector angular-spectrum with that n.

Coherence Handling

Spatial coherent: sum complex fields over sources.

Spatial incoherent: sum intensities over sources.

Spatial partial: coherent-mode decomposition of the cross-spectral density (CSD) on the source plane. Compute modes via FFT-based Hermitian eigensolve until residual trace ≤ ε.

Temporal coherent: sum complex over λ samples then square.

Temporal incoherent: intensity average over λ with weights S(λ).

Spectral sampling: choose Nλ adaptively until detector power and PSF metrics converge within ε.

System Architecture
/engine
  /core
    field_formats.hpp     // complex vector textures, packing
    fft_backend.hpp       // GPU FFT wrapper
    spectrum.hpp          // S(λ) sampler
    coherence.hpp         // spatial/temporal combiner
  /propagation
    vas_propagator.cs     // vector angular-spectrum kernel
    projector.cs          // k-space transversality projector
    evanescent_gate.cs    // stability guards
  /interfaces
    stratton_chu.cs       // dyadic Green surface integral over meshes
    mesh_sampler.cs       // interpolate tangential E,H on surface
    material_dispersion.hpp// Sellmeier eval
  /sources
    source_map_loader.cpp // image→{A,φ,p̂}
    source_field_init.cs  // place dipoles/point sources on plane
  /apertures
    absorbing_mask.cs     // binary mask via mesh or texture
  /detector
    resample.cs           // detector grid sampling
    metrics.cpp           // energy, MTF, Strehl
  /io
    config_io.cpp         // JSON
    dump_textures.cpp     // EXR/PNG
/ui
  controls.json/ui
/tests
  unit_*.cpp ; scenes/*

Data Formats

Complex vector field per plane: 6 channels. Pack as two RGBA32F textures: Re[Ex,Ey,Ez, pad], Im[Ex,Ey,Ez, pad].

K-space arrays: RGBA32F per component.

Detector: R32F intensity plus optional Stokes I,Q,U,V.

Pipeline

Load config. Build scene graph ordered by z. Insert planes before/after each interface.

Build λ samples {λ_k, w_k} from S(λ) with adaptive quadrature.

Build source set from source_map. For each source pixel i:

Initialize vector field on source plane as a point dipole of polarization p̂_i with complex amplitude A_i e^{iφ_i}. Sum on GPU (coherent) or mark as separate channel (incoherent).

For each λ_k:

If spatially incoherent: loop sources, compute intensities, accumulate weighted.

Else:

Start with E on current plane.

For each segment:
a) Homogeneous segment (free space or inside lens bulk): vector angular-spectrum propagate by Δz in the correct n(λ_k). Include evanescent.
b) Interface surface (air→glass or glass→air): evaluate Stratton–Chu on the triangulated surface to produce transmitted field in the next medium. Use correct k for each side. Reflection term optional if you want AR coatings; include if realism requires.
c) Aperture: zero field outside aperture mesh footprint (perfect absorber).

At detector z: write complex E_k.

Temporal combine:

temporal coherent: accumulate complex E += √w_k E_k

temporal incoherent: accumulate I += w_k |E_k|^2

Spatial combine (if incoherent sources): sum per-source intensities.

Outputs:

I(x,y,z) as requested slices.

Detector I_det(u,v).

Optional E(x,y,z) for debugging.

Numerical Guarantees

Sampling:

Grid Δx,Δy chosen so max transverse spatial frequency from geometry and NA satisfies k_t,max < π/Δx. Compute from largest aperture and shortest λ.

Padding to suppress wrap-around in FFT propagation.

Evanescent handling: keep modes with decay length > slice spacing; drop below tolerance to save compute.

Projector stability: clamp very low |k| to avoid division spikes.

Convergence:

Spectral: increase Nλ until detector power changes < ε_power and Strehl change < ε_psf.

CSD modes: include modes until residual trace < ε_csd.

Energy checks at each step (account for absorption and Fresnel losses).

Configuration Example
{
  "lambda_nm": 532.0,
  "bandwidth_nm": 1.0,
  "spectrum": "gaussian",
  "coherence": {"spatial": "coherent", "temporal": "incoherent"},
  "detector": {"pixels_x": 1024, "pixels_y": 1024, "pitch_m": 4e-6, "z_m": 0.25},
  "domain": {"extent_x_m": 8e-3, "extent_y_m": 8e-3, "Nxy": 2048},
  "lenses": [{
    "pose": {"x":0, "y":0, "z":0.10, "rx":0, "ry":0, "rz":0},
    "material": "N-BK7",
    "surfaces": {"S1_mesh":"assets/lens1_S1.obj","S2_mesh":"assets/lens1_S2.obj"},
    "aperture_radius_m": 3.0e-3,
    "f_m_hint": 0.10
  }],
  "apertures": [{"mesh":"assets/stop1.obj"}],
  "source_map_path": "assets/sources.png"
}

Kernels (compute-shader contracts)

CS_VAS_ProjectAndPropagate(tex_ReIm, n, dz): FFT 2D per vector component, apply projector P(k), multiply exp(i kz dz), iFFT.

CS_StrattonChu(surface_mesh, E_tan, H_tan, obs_plane): for each obs pixel, integrate dyadic Green over triangles. Quadrature order selectable. Supports near field.

CS_SourceInit(source_map): stamp vector dipoles at source plane.

CS_ApertureMask(mask_mesh_or_tex): zero out outside mask.

CS_DetectorSample(tex_ReIm): write intensity and optional Stokes.

Validation Scenes

Vector plane wave through tilted glass slab: compare to analytic Fresnel vector solution.

Focus by spherical biconvex mesh lens: compare to reference boundary-element solver.

Aperture diffraction at high NA: verify longitudinal E_z emergence.

Partial temporal coherence: bandwidth sweep vs contrast on detector.

Energy conservation across interfaces with and without reflections.

Deliverables for Agents

Claude: implement CS_VAS_ProjectAndPropagate, CS_StrattonChu skeletons, packing formats, FFT wrapper, and projector math. Provide unit tests with known analytic cases.

Cursor: wire config I/O, scene graph execution, adaptive samplers (λ and modes), and visualization. Add EXR dumps and convergence logs.

Notes

Lens meshes are required for exact interface handling. If only f_m is given, auto-generated spherical meshes are created to match f_m at λ0 via ray-exact geometry. Provide explicit meshes for true “no-approximation” behavior.

Sum of electric fields is the core accumulator. Intensities derived last.