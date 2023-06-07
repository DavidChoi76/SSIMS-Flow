"""
This is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This package is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this package. If not, you can get eh GNU GPL from
https://www.gnu.org/licenses/gpl-3.0.en.html.

Created by Robert Ljubicic.
"""


try:
	from __init__ import *
	from os import path
	from feature_tracking import fresh_folder
	from math import log10, floor
	from glob import glob
	from class_console_printer import Console_printer, tag_string, tag_print, unix_path
	from class_progress_bar import Progress_bar
	from class_timing import Timer, time_hms
	from CPP.dll_import import DLL_Loader
	from skimage.measure import block_reduce
	from ctypes import c_int, c_double, c_size_t
	from warnings import catch_warnings, simplefilter
	from vel_ratio import vel_ratio, L0
	from utilities import cfg_get

	import matplotlib.pyplot as plt

	dll_path = path.split(path.realpath(__file__))[0]
	dll_name = 'CPP/pooling.dll'
	dll_loader = DLL_Loader(dll_path, dll_name)
	# double mag_pool(float* array, size_t size, double m, int iter)
	mag_pool = dll_loader.get_function('double', 'mag_pool', ['float*', 'size_t', 'double', 'int'])
	
except Exception:
	print()
	tag_print('exception', 'Import failed! \n')
	print('\n{}'.format(format_exc()))
	input('\nPress ENTER/RETURN key to exit...')
	exit()


DISPLACEMENT_THRESHOLD = 0.85


def get_angle_range(angle_main, angle_range):
	angle_lower = angle_main - angle_range
	angle_upper = angle_main + angle_range

	underflow = True if angle_lower < 0 else False
	overflow = True if angle_upper >= 360 else False

	angle_lower = angle_lower + 360 if underflow else angle_lower
	angle_upper = angle_upper - 360 if overflow else angle_upper

	func = np.bitwise_or if overflow or underflow else np.bitwise_and

	return func, angle_lower, angle_upper


def pooling_mask(array, axis: int):
	res = np.ndarray(array.shape[:2])

	for i in range(res.shape[0]):
		for j in range(res.shape[1]):
			subarray = array[i, j, :, :]
			res[i, j] = mag_pool(subarray.ravel(), c_size_t(subarray.size), c_double(-1.0), c_int(1))

	return res


def nan_locate(y):
	return np.isnan(y), lambda z: z.nonzero()[0]


if __name__ == '__main__':
	try:
		parser = ArgumentParser()
		parser.add_argument('--cfg', type=str, help='Path to configuration file')
		args = parser.parse_args()

		cfg = configparser.ConfigParser()
		cfg.optionxform = str

		try:
			cfg.read(args.cfg, encoding='utf-8-sig')
		except Exception:
			tag_print('error', 'There was a problem reading the configuration file!')
			tag_print('error', 'Check if project has valid configuration.')
			input('\nPress ENTER/RETURN key to exit...')
			exit()
		
		section = 'Optical flow'

		project_folder = unix_path(cfg['Project settings']['Folder'])
		frames_folder = unix_path(cfg[section]['Folder'])
		results_folder = unix_path('{}/optical_flow'.format(cfg['Project settings']['Folder']))
		ext = cfg[section]['Extension']
		optical_flow_step = cfg_get(cfg, section, 'Step', int, 1)
		pairing = cfg_get(cfg, section, 'Pairing', int, 0)		# 0 = stepwise, 1 = sliding by 1
		scale = cfg_get(cfg, section, 'Scale', float, 1.0)
		pooling = cfg_get(cfg, section, 'Pooling', int)
		angle_main = cfg_get(cfg, section, 'AngleMain', float)
		angle_range = cfg_get(cfg, section, 'AngleRange', float)
		average_only = cfg_get(cfg, section, 'AverageOnly', int, 0)
		live_preview = cfg_get(cfg, section, 'LivePreview', int, 0)

		fresh_folder(results_folder, exclude=['depth_profile.txt'])
		fresh_folder(results_folder + '/magnitudes')
		fresh_folder(results_folder + '/directions')
		fresh_folder(results_folder + '/diagnostics')
		
		paths_frames = glob('{}/*.{}'.format(frames_folder, ext))
		num_frames = len(paths_frames)
		num_digits = floor(log10(num_frames)) + 1
		angle_func, angle_lower, angle_upper = get_angle_range(angle_main, angle_range)
		
		if pairing == 0:
			paths_frame_A = paths_frames[0:-optical_flow_step:optical_flow_step]
			paths_frame_B = paths_frames[optical_flow_step::optical_flow_step]
		elif pairing == 1:
			paths_frame_A = paths_frames[:-optical_flow_step]
			paths_frame_B = paths_frames[optical_flow_step:]
		elif pairing == 2:
			paths_frame_B = paths_frames[optical_flow_step::optical_flow_step]
			paths_frame_A = paths_frames[0] * len(paths_frame_B)
		
		indices_frame_A = [paths_frames.index(x) for x in paths_frame_A]
		indices_frame_B = [paths_frames.index(x) for x in paths_frame_B]

		assert len(paths_frame_A) == len(paths_frame_B), f'Frames A list length = {len(paths_frame_A)} != Frames B list length = {len(paths_frame_B)}'
		num_frame_pairs = len(paths_frame_A)

		frame_A = cv2.imread(paths_frame_A[0], 0)
		h, w = frame_A.shape

		# Xmin = cfg_get(cfg, section, 'Xmin', int, 0)
		# Xmax = cfg_get(cfg, section, 'Xmax', int, w)
		# Ymin = cfg_get(cfg, section, 'Ymin', int, 0)
		# Ymax = cfg_get(cfg, section, 'Ymax', int, h)

		# crop = 0 if (abs(Xmax - Xmin) == w and abs(Ymax - Ymin) == h) else 1

		farneback_pyr_scale = 0.5
		farneback_pyr_levels = 3
		farneback_avg_win = 15
		farneback_iters = 2
		farneback_poly_win = 7
		farneback_sigma = 1.5

		farneback_params = [farneback_pyr_scale,
		      				farneback_pyr_levels,
							farneback_avg_win,
							farneback_iters,
							farneback_poly_win,
							farneback_sigma,
							0]
	
		if scale != 1.0:
			frame_A = cv2.resize(frame_A, (int(w * scale), int(h * scale)))
			h, w = frame_A.shape

		h_pooled = int(np.ceil(h/pooling))
		w_pooled = int(np.ceil(w/pooling))
		padd_h = h_pooled//10
		padd_w = w_pooled//10

		flow_hsv = np.zeros([h_pooled, w_pooled, 2], dtype='uint8')
		mag_stack = np.zeros([h_pooled, w_pooled, num_frame_pairs], dtype='float32')
		mag_max = np.zeros(mag_stack.shape[:2])
		angle_stack = np.zeros(mag_stack.shape)

		coverage_list = np.zeros(num_frame_pairs, dtype='float32')
		disp_mean_list = np.zeros(num_frame_pairs, dtype='float32')
		disp_median_list = np.zeros(num_frame_pairs, dtype='float32')
		disp_max_list = np.zeros(num_frame_pairs, dtype='float32')

		if live_preview:
			fig, ax = plt.subplots()

			try:
				mng = plt.get_current_fig_manager()
				mng.window.state('zoomed')
				mng.set_window_title('Optical flow')
			except Exception:
				pass

			background = plt.imshow(frame_A, cmap='gray', extent=[-0.5, mag_max.shape[1], mag_max.shape[0], -0.5])
			flow_shown = plt.imshow(flow_hsv[:, :, 0], cmap='jet', alpha=0.5)

			cbar = plt.colorbar(flow_shown)
			cbar.solids.set(alpha=1.0)
			cbar.set_label('Velocity magnitude [px/frame]')
			
			plt.title('Frames {}+{} of {} total'.format(indices_frame_A[0], indices_frame_B[0], num_frames))
			plt.axis('off')
			plt.tight_layout()

		console_printer = Console_printer()
		progress_bar = Progress_bar(total=num_frame_pairs, prefix=tag_string('info', 'Frame pair '))
		timer = Timer(total_iter=num_frame_pairs)

		tag_print('start', 'Optical flow estimation using Farneback algorithm\n')
		tag_print('info', 'Using frames from folder [{}]'.format(frames_folder))
		tag_print('info', 'Frame extension = {}'.format(ext))
		tag_print('info', 'Number of frames = {}'.format(num_frames))
		tag_print('info', 'Number of frame pairs = {}'.format(num_frame_pairs))
		tag_print('info', 'Optical flow step = {}'.format(optical_flow_step))
		tag_print('info', 'Frame scaling = {:.1f}'.format(scale))
		tag_print('info', 'Pooling = {} px'.format(pooling))
		tag_print('info', 'Main flow direction = {:.0f} deg'.format(angle_main))
		tag_print('info', 'Direction range = {:.0f} deg\n'.format(angle_range))
		tag_print('info', 'Starting motion detection...\n')

		j = 0

		for i in range(num_frame_pairs):
			if i > 0 and paths_frame_A[i] == paths_frame_B[i-1]:
				frame_A = frame_B
			else:
				frame_A = cv2.imread(paths_frame_A[i], 0)
				
			frame_B = cv2.imread(paths_frame_B[i], 0)

			if scale != 1.0:
				frame_A = cv2.resize(frame_A, (w, h))
				frame_B = cv2.resize(frame_B, (w, h))

			# if crop:
			# 	frame_A_crop = frame_A[int(Ymin*scale): int(Ymax*scale), int(Xmin*scale): int(Xmax*scale)]
			# 	frame_B_crop = frame_B[int(Ymin*scale): int(Ymax*scale), int(Xmin*scale): int(Xmax*scale)]

			# 	flow = np.zeros([h, w, 2], dtype='float32')
			# 	flow_crop = cv2.calcOpticalFlowFarneback(frame_A_crop, frame_B_crop, None, *farneback_params)
			# 	flow[int(Ymin*scale): int(Ymax*scale), int(Xmin*scale): int(Xmax*scale), :] = flow_crop
			# else:
			# 	flow = cv2.calcOpticalFlowFarneback(frame_A, frame_B, None, *farneback_params)
			flow = cv2.calcOpticalFlowFarneback(frame_A, frame_B, None, *farneback_params)

			magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=True)
			# magnitude[magnitude < DISPLACEMENT_THRESHOLD] = 0

			# Filter by vector angle
			angle = np.where(angle_func((angle >= angle_lower), (angle <= angle_upper)), angle, np.NaN)
			mask_magnitude = np.where(angle >= 0, 1, 0)
			magnitude *= mask_magnitude

			if angle_func.__name__ == "bitwise_or":
				angle -= angle_upper
				angle = np.where(angle <= 0, angle + 360, angle)

			if pooling > 1:
				with catch_warnings():
					simplefilter("ignore", category=RuntimeWarning)
					magnitude = block_reduce(magnitude, (pooling, pooling), pooling_mask)
					angle = block_reduce(angle, (pooling, pooling), np.nanmean)

			mag_stack[:, :, j] = magnitude
			mag_max = np.maximum(mag_max, magnitude)

			disp_nonzero = magnitude[magnitude > DISPLACEMENT_THRESHOLD]
			disp_coverage = np.where(magnitude > DISPLACEMENT_THRESHOLD, 1, 0).sum() / magnitude.size * 100
			disp_mean = disp_nonzero.mean() if disp_nonzero.size > 0 else 0
			disp_median = np.median(disp_nonzero) if disp_nonzero.size > 0 else 0
			disp_max = np.max(magnitude)

			coverage_list[i] = disp_coverage
			disp_mean_list[i] = disp_mean
			disp_median_list[i] = disp_median
			disp_max_list[i] = disp_max

			nans, x = nan_locate(angle)
			try:
				if 315 <= angle_main <= 360 or \
					 0 <= angle_main <= 45 or \
				   135 <= angle_main <= 225:
					angle[nans] = np.interp(x(nans), x(~nans), angle[~nans], period=360)
				else:
					angle[nans] = np.interp(x(nans.T), x(~nans.T), angle[~nans].T, period=360).T
			except ValueError:
				pass

			angle_stack[:, :, j] = angle

			if not average_only:
				n = str(i).rjust(num_digits, '0')
				np.savetxt('{}/magnitudes/{}.txt'.format(results_folder, n), magnitude, fmt='%.2f')
				np.savetxt('{}/directions/{}.txt'.format(results_folder, n), angle, fmt='%.1f')

			if live_preview:
				max_cbar = np.max(mag_max[padd_h: -padd_h, padd_w: -padd_w])

				background.set_data(frame_B)
				flow_shown.set_data(mag_max)
				flow_shown.set_clim(vmax=max_cbar, vmin=0)

				cbar.solids.set(alpha=1.0)
				
				plt.title('Frames {}+{} of {} total'.format(indices_frame_A[i], indices_frame_B[i], num_frames))
				plt.pause(0.001)
				plt.draw()

			timer.update()

			console_printer.add_line(progress_bar.get(i))
			console_printer.add_line(
				tag_string('info', 'Frames {}+{} of {} total'
		   			.format(indices_frame_A[i], indices_frame_B[i], num_frames)
				)
			)
			
			console_printer.add_line(
				tag_string('info', 'Frame processing time = {:.3f} sec'
					.format(timer.interval())
				)
			)
			console_printer.add_line(
				tag_string('info', 'Elapsed time = {} hr {} min {} sec'
					.format(*time_hms(timer.elapsed()))
				)
			)
			console_printer.add_line(
				tag_string('info', 'Remaining time = {} hr {} min {} sec'
					.format(*time_hms(timer.remaining()))
				)
			)

			console_printer.add_line(tag_string('info', 'Detection metrics:'))
			console_printer.add_line(' '*11 + 'Coverage =             {:.2f} %'.format(disp_coverage))
			console_printer.add_line(' '*11 + 'Mean displacement =    {:.3f} px'.format(disp_mean))
			console_printer.add_line(' '*11 + 'Median displacement =  {:.3f} px'.format(disp_median))
			console_printer.add_line(' '*11 + 'Maximal displacement = {:.3f} px'.format(disp_max))

			console_printer.overwrite()
			
			j += 1

		print()
		tag_print('info', 'Starting temporal filtering...\n')

		console_printer.reset()
		progress_bar = Progress_bar(total=mag_stack.shape[0] * mag_stack.shape[1], prefix=tag_string('info', 'Filtering '))
		
		m = 0
		threshold_ratios = np.ndarray(mag_stack.shape[:2], dtype='float32')
		mag_mean = np.ndarray(mag_stack.shape[:2], dtype='float32')

		T0_array = np.zeros(mag_stack.shape[:2], dtype='float32')
		T1_array = np.zeros(mag_stack.shape[:2], dtype='float32')
		T2_array = np.zeros(mag_stack.shape[:2], dtype='float32')

		for i in range(mag_stack.shape[0]):
			for j in range(mag_stack.shape[1]):
				mags_xy = mag_stack[i, j, :]

				# Threshold means
				# T0 = threshold is the global mean, average the rest
				# T1 = threshold is T0, average the rest
				# T2 = threshold is T1, average the rest
				T0 = mag_pool(mags_xy.ravel(), c_size_t(mags_xy.size), c_double(-1.0), c_int(1))
				T1 = mag_pool(mags_xy.ravel(), c_size_t(mags_xy.size), c_double(T0), c_int(1))
				T2 = mag_pool(mags_xy.ravel(), c_size_t(mags_xy.size), c_double(T1), c_int(1))

				T0_array[i, j] = T0
				T1_array[i, j] = T1
				T2_array[i, j] = T2

				# Final velocity:
				# close to T0 if signal too noisy, likely not water surface,
				# close to T1 for dense seeding,
				# close to T2 if sparse seeding
				threshold_ratios[i, j] = (T2 - T1)/(T1 - T0) if T1 != T0 else L0
				mag_mean[i, j] = vel_ratio(T0, T1, T2)

				console_printer.add_line(progress_bar.get(m))
				console_printer.overwrite()
				m += 1

		angle_mean = np.nanmean(angle_stack, axis=2)
		if angle_func.__name__ == "bitwise_or":
			angle_mean += angle_upper
			angle_mean = np.where(angle_mean >= 360, angle_mean - 360, angle_mean)

		np.savetxt('{}/diagnostics/T0.txt'.format(results_folder), T0_array, fmt='%.3f')
		np.savetxt('{}/diagnostics/T1.txt'.format(results_folder), T1_array, fmt='%.3f')
		np.savetxt('{}/diagnostics/T2.txt'.format(results_folder), T2_array, fmt='%.3f')

		np.savetxt('{}/diagnostics/coverage.txt'.format(results_folder), coverage_list, fmt='%.3f')
		np.savetxt('{}/diagnostics/disp_mean.txt'.format(results_folder), disp_mean_list, fmt='%.3f')
		np.savetxt('{}/diagnostics/disp_median.txt'.format(results_folder), disp_median_list, fmt='%.3f')
		np.savetxt('{}/diagnostics/disp_max.txt'.format(results_folder), disp_max_list, fmt='%.3f')

		np.savetxt('{}/mag_mean.txt'.format(results_folder), mag_mean, fmt='%.3f')
		np.savetxt('{}/mag_max.txt'.format(results_folder), mag_max, fmt='%.3f')
		np.savetxt('{}/angle_mean.txt'.format(results_folder), angle_mean, fmt='%.3f')
		np.savetxt('{}/threshold_ratios.txt'.format(results_folder), threshold_ratios, fmt='%.3f')
		
		print()
		tag_print('end', 'Optical flow estimation complete!')
		tag_print('end', 'Results available in [{}]!'.format(results_folder))
		print('\a')
		input('\nPress ENTER/RETURN key to exit...')

	except Exception as ex:
		print()
		tag_print('exception', 'An exception has occurred! See traceback bellow: \n')
		print('\n{}'.format(format_exc()))
		input('\nPress ENTER/RETURN key to exit...')
