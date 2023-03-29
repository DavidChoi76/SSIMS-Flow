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
	from class_console_printer import tag_print
	from CPP.dll_import import DLL_Loader
	from ctypes import c_size_t, c_double

	import scipy.stats as stats

	dll_path = path.split(path.realpath(__file__))[0]
	dll_name = 'CPP/filtering.dll'
	dll_loader = DLL_Loader(dll_path, dll_name)
	cpp_intensity_capping = dll_loader.get_function('void', 'intensity_capping', ['byte*', 'size_t', 'double'])

except Exception as ex:
	print()
	tag_print('exception', 'Import failed! \n')
	print('\n{}'.format(format_exc()))
	input('\nPress ENTER/RETURN key to exit...')
	exit()

colorspaces_list = ['rgb', 'hsv', 'lab', 'grayscale']
color_conv_codes = [
	[[], 	[41], 		[45], 		[7]],
	[[55], 	[], 		[55, 45], 	[55, 7]],
	[[57], 	[57, 41], 	[], 		[57, 7]],
	[[8], 	[8, 41], 	[8, 45], 	[]]
]

colorspace = 'rgb'


def three_channel(img):
	try:
		a = img[:, :, 0]
		return img
	except IndexError:
		return cv2.merge([img, img, img])


def convert_img(img: str, from_cs: str, to_cs: str) -> np.ndarray:
	global colorspace
	"""
	Convert image from one colorspace to another. Extends cv2.cvtColor() to
	encompass all transformation possibilities between RGB, HSV, LAB, and grayscale.
	"""

	colorspace = to_cs

	from_cs_index = colorspaces_list.index(from_cs)
	to_cs_index = colorspaces_list.index(to_cs)
	conv_codes = color_conv_codes[from_cs_index][to_cs_index]

	if to_cs == from_cs:
		return img

	if from_cs == 'grayscale':
		try:
			img = img[:, :, 0]
		except IndexError:
			pass

	if len(conv_codes) == 0:
		return img
	
	for code in conv_codes:
		img = cv2.cvtColor(img, code)

	return three_channel(img)


def is_grayscale(img: np.ndarray) -> bool:
	"""
	Checks whether all three image channels are identical,
	i.e., if image is grayscale.
	"""
	try:
		img[:, :, 0]
	except IndexError:
		return True
	
	if (img[:, :, 0] == img[:, :, 1]).all() and (img[:, :, 0] == img[:, :, 2]).all():
		return True
	else:
		return False


def func(name, image, params):
	"""
	Template function for all filtering functions.
	"""
	return name(image, *params)


def crop(img, xs, xe, ys, ye):
	return img[xs: xe, ys: ye, :]

	
def negative(img):
	return ~img


def to_grayscale(img):
	img_gray = convert_img(img, colorspace, 'grayscale')
	return cv2.merge([img_gray, img_gray, img_gray])


def to_rgb(img):
	return convert_img(img, colorspace, 'rgb')
	
	
def to_hsv(img):
	return convert_img(img, colorspace, 'hsv')
	

def to_lab(img):
	return convert_img(img, colorspace, 'lab')


def rearrange_channels(img, c1=1, c2=2, c3=3):
	return cv2.merge([img[:, :, int(c1 - 1)], img[:, :, int(c2 - 1)], img[:, :, int(c3 - 1)]])
	

def select_channel(img, channel=1):
	global colorspace

	try:
		img_single = img[:, :, int(channel)-1]
	except IndexError:
		return img

	colorspace = 'grayscale'
	return cv2.merge([img_single, img_single, img_single])
	
	
def highpass(img, sigma=51):
	if sigma % 2 == 0:
		sigma += 1

	if is_grayscale(img):
		img = img[:, :, 0]
	
	blur = cv2.GaussianBlur(img, (0, 0), int(sigma))
	img_highpass = ~cv2.subtract(cv2.add(blur, 127), img)

	return three_channel(img_highpass)


def bilateral_highpass(img, d=-1, sigma=51):
	bilateral = cv2.bilateralFilter(img, d, sigma, sigma)
	img_highpass = cv2.subtract(img, bilateral)

	return three_channel(img_highpass)
	
	
def normalize_image(img, lower=None, upper=None):
	img_gray = convert_img(img, colorspace, 'grayscale')[:, :, 0]
	
	if lower is None:
		lower = 0
	if upper is None:
		upper = 255

	img_norm = ((img_gray - lower) / (upper - lower) * 255).astype('uint8')

	return cv2.merge([img_norm, img_norm, img_norm])


def intensity_capping(img, n_std=0.0, mode=1):
	img_gray = convert_img(img, colorspace, 'grayscale')[:, :, 0]
	img_gray = ~img_gray if mode == 1 else img_gray

	img_ravel = img_gray.ravel()
	cpp_intensity_capping(img_ravel, c_size_t(img_ravel.size), c_double(n_std))
	img_cap = ~img_ravel.reshape(img_gray.shape) if mode == 1 else img_ravel.reshape(img_gray.shape)

	return cv2.merge([img_cap, img_cap, img_cap])
	
	
def brightness_contrast(img, alpha=1.0, beta=0.0):
	return cv2.convertScaleAbs(img, alpha=alpha, beta=beta)


def adjust_channels(img, shift_c1=0, shift_c2=0, shift_c3=0):
	c1, c2, c3 = cv2.split(img)

	c1 = cv2.add(c1, shift_c1)
	c2 = cv2.add(c2, shift_c2)
	c3 = cv2.add(c3, shift_c3)

	return cv2.merge([c1, c2, c3])


def gamma(img, gamma=1.0):
	invGamma = 1.0 / gamma
	
	table = np.array([((i / 255.0) ** invGamma) * 255
		for i in np.arange(0, 256)]).astype("uint8")
		
	return cv2.LUT(img, table)


def gaussian_lookup(img, sigma=51, mean=127):
	x = np.arange(0, 256)
	pdf = stats.norm.pdf(x, mean, sigma)

	cdf = np.cumsum(pdf)
	cdf_norm = np.array([(x - np.min(cdf))/(np.max(cdf) - np.min(cdf)) * 255 for x in cdf]).astype('uint8')

	return cv2.LUT(img, cdf_norm)
	
	
def thresholding(img, c1l=0, c1u=255, c2l=0, c2u=255, c3l=0, c3u=255):
	global colorspace
	
	mask = cv2.inRange(img, (int(c1l), int(c2l), int(c3l)), (int(c1u), int(c2u), int(c3u)))
	
	colorspace = 'grayscale'
	return cv2.merge([mask, mask, mask])


def denoise(img, ksize=3):
	return cv2.medianBlur(img, int(ksize))


def channel_ratios(img, c1=1, c2=2, limit=2.0):
	divisor = img[:, :, int(c2 - 1)]
	divisor[divisor == 0] = 255

	print(np.min(divisor))

	ratio = img[:, :, int(c1 - 1)].astype('float') / divisor.astype('float')
	ratio[ratio > limit] = limit
	ratio = ((ratio - np.min(ratio)) / (np.max(ratio) - np.min(ratio)) * 255).astype('uint8')

	return cv2.merge([ratio, ratio, ratio])


def histeq(img):
	img_gray = convert_img(img, colorspace, 'grayscale')[:, :, 0]
	eq = cv2.equalizeHist(img_gray)
	
	return convert_img(eq, 'grayscale', colorspace)


def clahe(img, clip=2.0, tile=8):
	img_gray = convert_img(img, colorspace, 'grayscale')[:, :, 0]
	clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(int(tile), int(tile)))
	img_clahe = clahe.apply(img_gray)
	
	return convert_img(img_clahe, 'grayscale', colorspace)

# Background removal filter has to remain in other scripts
# because it needs more than one frame to work.
